"""Muslim Prayer Companion Coordinator."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api_providers import CalculatedProvider, IrelandProvider, PrayerTimesProvider
from .api_providers.base import (
    PrayerTimesData,
    ProviderConfig,
    ProviderError,
    ProviderResponseError,
    ProviderResult,
)
from .const import (
    ALL_PRAYER_TIMES,
    DEFAULT_FALLBACK_CALC_METHOD,
    DOMAIN,
    EVENT_PRAYER_TIME,
    IQAMAH_METHOD_API,
    ISSUE_PROVIDER_FALLBACK,
    LOGGER,
    PRAYERS,
    RETRY_DELAYS,
    UPDATE_INTERVAL_MINUTES,
)
from .helpers.derived import DerivedInputs, compute_derived
from .helpers.friday import FridayPrayersFetcher, FridayPrayerTimes
from .helpers.iqamah import IqamahApiClient
from .helpers.qibla import calculate_qibla_direction
from .helpers.settings import Settings

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from homeassistant.config_entries import ConfigEntry

ERROR_PLACEHOLDER_CHARS = 200


def fallback_issue_id(entry_id: str) -> str:
    """Return the Repairs issue id used while an entry runs on fallback times."""
    return f"{ISSUE_PROVIDER_FALLBACK}_{entry_id}"


class MuslimPrayerCompanionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch prayer times once an hour and recompute derived values every minute."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator for one config entry."""
        self.settings = Settings.from_entry(config_entry)
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        try:
            self.tz = ZoneInfo(self.settings.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            LOGGER.warning(
                "Unknown time zone %r for %s, using the Home Assistant time zone",
                self.settings.timezone,
                self.settings.location_name,
            )
            self.tz = dt_util.get_default_time_zone()

        self.event_unsub: CALLBACK_TYPE | None = None
        self._tick_unsub: CALLBACK_TYPE | None = None
        self._retry_unsub: CALLBACK_TYPE | None = None
        self._retry_attempt = 0

        self._session: ClientSession = async_get_clientsession(hass)
        self._provider: PrayerTimesProvider = self._build_provider()
        self._fallback_provider: CalculatedProvider | None = None
        self._in_fallback = False
        self._last_error: str | None = None

        self._raw: ProviderResult | None = None
        self._raw_date: date | None = None
        self._last_tick: datetime = dt_util.utcnow()

        self._friday_fetcher = FridayPrayersFetcher(
            self._session, self.settings.friday_mosques, self.tz
        )
        self._friday: list[FridayPrayerTimes] = []
        self._iqamah_client: IqamahApiClient | None = None
        if self.settings.iqamah_method == IQAMAH_METHOD_API and self.settings.iqamah_api_url:
            self._iqamah_client = IqamahApiClient(
                self._session, self.settings.iqamah_api_url, self.tz
            )
        self._iqamah_api = None
        self._qibla = calculate_qibla_direction(self.settings.latitude, self.settings.longitude)

    # --- Public properties ----------------------------------------------------

    @property
    def latitude(self) -> float:
        """Return the configured latitude."""
        return self.settings.latitude

    @property
    def longitude(self) -> float:
        """Return the configured longitude."""
        return self.settings.longitude

    @property
    def location_name(self) -> str:
        """Return the configured location name."""
        return self.settings.location_name

    @property
    def calc_method(self) -> str:
        """Return the calculation method (or mosque key for Irish entries)."""
        return self.settings.calc_method

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return self.settings.source_type

    @property
    def iqamah_method(self) -> str:
        """Return the iqamah method."""
        return self.settings.iqamah_method

    @property
    def provider(self) -> PrayerTimesProvider:
        """Return the primary provider."""
        return self._provider

    @property
    def provider_name(self) -> str:
        """Return a human readable name of the primary source."""
        if isinstance(self._provider, IrelandProvider):
            return self._provider.api_name
        return f"Calculated ({self.settings.calc_method.upper()})"

    @property
    def fallback_active(self) -> bool:
        """Return True while prayer times come from the calculated fallback."""
        return self._in_fallback

    @property
    def last_error(self) -> str | None:
        """Return the last provider error, if any."""
        return self._last_error

    @property
    def raw_result(self) -> ProviderResult | None:
        """Return the last provider result."""
        return self._raw

    # --- Providers --------------------------------------------------------------

    def _build_provider(self) -> PrayerTimesProvider:
        config = ProviderConfig(
            latitude=self.settings.latitude,
            longitude=self.settings.longitude,
            calculation_method=self.settings.calc_method,
            timezone=self.settings.timezone,
        )
        if self.settings.is_ireland:
            return IrelandProvider(config, self._session)
        if self.settings.source_type != "calculated":
            LOGGER.warning(
                "Mosque %r is no longer known; %s will use the calculated %s method",
                self.config_entry.data.get("calculation_method"),
                self.settings.location_name,
                DEFAULT_FALLBACK_CALC_METHOD,
            )
            config.calculation_method = DEFAULT_FALLBACK_CALC_METHOD
        return CalculatedProvider(config, self._session)

    def _get_fallback_provider(self) -> CalculatedProvider:
        if self._fallback_provider is None:
            self._fallback_provider = CalculatedProvider(
                ProviderConfig(
                    latitude=self.settings.latitude,
                    longitude=self.settings.longitude,
                    calculation_method=DEFAULT_FALLBACK_CALC_METHOD,
                    timezone=self.settings.timezone,
                ),
                self._session,
            )
        return self._fallback_provider

    # --- Refresh ----------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Start the per-minute tick once, before the first refresh."""
        if self._tick_unsub is None:
            self._tick_unsub = async_track_time_change(self.hass, self._async_minute_tick, second=0)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch prayer times and build the data dict."""
        now = dt_util.utcnow()
        today = dt_util.now().date()

        try:
            result = await self._provider.async_fetch(today)
        except ProviderError as err:
            result = await self._async_handle_failure(today, err)
        except Exception as err:  # noqa: BLE001 - anything unexpected is still "source down"
            LOGGER.debug("Unexpected error from %s", self.provider_name, exc_info=err)
            result = await self._async_handle_failure(
                today, ProviderResponseError(f"{type(err).__name__}: {err}")
            )
        else:
            self._async_clear_fallback()

        self._raw = result
        self._raw_date = today
        self._retry_attempt = 0
        self._cancel_retry()

        if self._iqamah_client is not None:
            self._iqamah_api = await self._iqamah_client.async_fetch(today)

        try:
            self._friday = await self._friday_fetcher.async_update(
                today, result, self.settings.mosque_key
            )
        except Exception:  # noqa: BLE001 - Friday data must never break the refresh
            LOGGER.exception("Could not update Friday prayer times for %s", self.location_name)

        self._schedule_midnight_refresh()
        self._last_tick = now
        return self._compute_derived(now)

    async def _async_handle_failure(self, today: date, err: ProviderError) -> ProviderResult:
        """Fall back to calculated times, or reuse today's last result, or fail."""
        self._last_error = str(err)

        if not isinstance(self._provider, CalculatedProvider):
            fallback = self._get_fallback_provider()
            try:
                result = await fallback.async_fetch(today)
            except ProviderError as fallback_err:
                LOGGER.warning(
                    "Fallback calculation for %s failed too: %s",
                    self.location_name,
                    fallback_err,
                )
            else:
                result.source = fallback.fallback_source_id
                result.today.source = result.source
                if result.tomorrow is not None:
                    result.tomorrow.source = result.source
                self._async_enter_fallback(err)
                return result

        if self._raw is not None and self._raw_date == today:
            LOGGER.warning(
                "Prayer times for %s could not be refreshed (%s); keeping today's times",
                self.location_name,
                err,
            )
            return self._raw

        self._schedule_retry()
        msg = f"Failed to fetch prayer times for {self.location_name}: {err}"
        raise UpdateFailed(msg) from err

    @callback
    def _async_enter_fallback(self, err: ProviderError) -> None:
        if self._in_fallback:
            LOGGER.debug("%s still on fallback times: %s", self.location_name, err)
            return
        self._in_fallback = True
        LOGGER.warning(
            "%s: %s is unavailable (%s); using calculated %s times until it recovers",
            self.location_name,
            self.provider_name,
            err,
            DEFAULT_FALLBACK_CALC_METHOD.upper(),
        )
        url = self._provider.url if isinstance(self._provider, IrelandProvider) else ""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            fallback_issue_id(self.config_entry.entry_id),
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_PROVIDER_FALLBACK,
            translation_placeholders={
                "location": self.location_name,
                "mosque": self.provider_name,
                "url": url,
                "error": str(err)[:ERROR_PLACEHOLDER_CHARS],
                "fallback": f"{DEFAULT_FALLBACK_CALC_METHOD.upper()} calculation",
            },
        )

    @callback
    def _async_clear_fallback(self) -> None:
        self._last_error = None
        if not self._in_fallback:
            return
        self._in_fallback = False
        ir.async_delete_issue(self.hass, DOMAIN, fallback_issue_id(self.config_entry.entry_id))
        LOGGER.info("%s: %s is available again", self.location_name, self.provider_name)

    # --- Scheduling -------------------------------------------------------------

    def _cancel_retry(self) -> None:
        if self._retry_unsub is not None:
            self._retry_unsub()
            self._retry_unsub = None

    def _schedule_retry(self) -> None:
        delay = RETRY_DELAYS[min(self._retry_attempt, len(RETRY_DELAYS) - 1)]
        self._retry_attempt += 1
        self._cancel_retry()
        LOGGER.debug("Retrying prayer times for %s in %s s", self.location_name, delay)
        self._retry_unsub = async_call_later(self.hass, delay, self._async_retry)

    async def _async_retry(self, _now: datetime) -> None:
        self._retry_unsub = None
        await self.async_request_refresh()

    def _schedule_midnight_refresh(self) -> None:
        if self.event_unsub is not None:
            self.event_unsub()
        next_midnight = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1)) + timedelta(
            seconds=1
        )
        self.event_unsub = async_track_point_in_time(
            self.hass, self._async_midnight_refresh, next_midnight
        )

    async def _async_midnight_refresh(self, _now: datetime) -> None:
        self.event_unsub = None
        await self.async_request_refresh()

    async def async_request_update(self, *_: Any) -> None:
        """Request an update from the coordinator (kept for compatibility)."""
        await self.async_request_refresh()

    @callback
    def _async_minute_tick(self, _now_local: datetime) -> None:
        """Recompute derived values and fire events, without any network access."""
        if self._raw is None:
            return
        if dt_util.now().date() != self._raw_date:
            # Midnight passed while we were asleep (suspend, clock jump): refetch.
            self.hass.async_create_task(self.async_request_refresh())
            return
        now = dt_util.utcnow()
        self._fire_events(self.data, self._last_tick, now)
        self._last_tick = now
        self.data = self._compute_derived(now)
        self.async_update_listeners()

    # --- Events -----------------------------------------------------------------

    def _fire_events(self, previous: dict[str, Any] | None, start: datetime, end: datetime) -> None:
        """Fire one event for every prayer/iqamah/Jumu'ah instant in ``(start, end]``."""
        if not previous:
            return

        def fire(event_type: str, when: datetime, **extra: Any) -> None:
            self.hass.bus.async_fire(
                EVENT_PRAYER_TIME,
                {
                    "type": event_type,
                    "entry_id": self.config_entry.entry_id,
                    "location_name": self.location_name,
                    "time": when.isoformat(),
                    **extra,
                },
            )

        def due(value: Any) -> bool:
            return isinstance(value, datetime) and start < value <= end

        for name in ALL_PRAYER_TIMES:
            if due(previous.get(name)):
                fire("prayer", previous[name], prayer=name)
        for prayer in PRAYERS:
            value = previous.get(f"iqamah_{prayer}")
            if due(value):
                fire("iqamah", value, prayer=prayer)
        if due(previous.get("imsak")):
            fire("imsak", previous["imsak"])
        for slug, info in (previous.get("friday") or {}).items():
            for session in (1, 2):
                value = info.get(f"jumuah_{session}")
                if due(value):
                    labels = info.get("labels") or []
                    fire(
                        "jumuah",
                        value,
                        mosque=info.get("name"),
                        slug=slug,
                        session=session,
                        label=labels[session - 1] if len(labels) >= session else None,
                    )

    # --- Derived data -----------------------------------------------------------

    def _compute_derived(self, now: datetime) -> dict[str, Any]:
        if self._raw is None:  # pragma: no cover - callers check first
            return {}
        return compute_derived(
            DerivedInputs(
                now=now,
                result=self._raw,
                tz=self.tz,
                settings=self.settings,
                qibla=self._qibla,
                provider_name=self.provider_name,
                friday=self._friday,
                iqamah_api=self._iqamah_api,
                fallback_active=self._in_fallback,
                last_error=self._last_error,
            )
        )

    # --- Service support --------------------------------------------------------

    async def async_prayer_times_for(self, day: date) -> PrayerTimesData:
        """
        Return the prayer times for ``day`` (cached today/tomorrow, else computed).

        Raises:
            HomeAssistantError: If the source cannot provide that date.
        """
        if self._raw is not None and self._raw_date is not None:
            if day == self._raw_date:
                return self._raw.today
            if self._raw.tomorrow is not None and day == self._raw_date + timedelta(days=1):
                return self._raw.tomorrow
        if self._provider.supports_any_date:
            try:
                return (await self._provider.async_fetch(day)).today
            except ProviderError as err:
                if isinstance(self._provider, CalculatedProvider):
                    raise HomeAssistantError(str(err)) from err
                return (await self._get_fallback_provider().async_fetch(day)).today
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="date_not_available",
            translation_placeholders={"source": self.provider_name, "date": str(day)},
        )

    # --- Shutdown ---------------------------------------------------------------

    async def async_shutdown(self) -> None:
        """Cancel timers and shut down."""
        if self.event_unsub is not None:
            self.event_unsub()
            self.event_unsub = None
        if self._tick_unsub is not None:
            self._tick_unsub()
            self._tick_unsub = None
        self._cancel_retry()
        await super().async_shutdown()
