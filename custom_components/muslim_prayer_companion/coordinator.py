"""Muslim Prayer Companion Coordinator."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_providers import CalculatedProvider, IrelandProvider, PrayerTimesProvider
from .api_providers.base import (
    ProviderConfig,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderValidationError,
)
from .const import (
    CONF_CALC_METHOD,
    CONF_IQAMAH_METHOD,
    CONF_IQAMAH_OFFSETS,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    DEFAULT_CALC_METHOD,
    DEFAULT_IQAMAH_METHOD,
    DEFAULT_IQAMAH_OFFSETS,
    DEFAULT_LOCATION_NAME,
    DEFAULT_SOURCE_TYPE,
    DOMAIN,
    IRELAND_CALC_METHODS,
    LOGGER,
    PRAYERS,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
)
from .helpers import get_hijri_date, get_special_night, is_friday, is_ramadan
from .helpers.qibla import calculate_qibla_direction

if TYPE_CHECKING:
    from aiohttp import ClientSession


class MuslimPrayerCompanionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Muslim Prayer Companion Data Update Coordinator.

    Supports multi-instance operation with per-entry configuration.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        latitude: float | None = None,
        longitude: float | None = None,
        location_name: str | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            config_entry: Config entry for this coordinator instance.
            latitude: Location latitude. Defaults to HA config latitude.
            longitude: Location longitude. Defaults to HA config longitude.
            location_name: Human-readable location name.
        """
        self.config_entry = config_entry
        self.event_unsub: CALLBACK_TYPE | None = None

        # Location configuration
        self._latitude = latitude or config_entry.data.get(
            CONF_LATITUDE, hass.config.latitude
        )
        self._longitude = longitude or config_entry.data.get(
            CONF_LONGITUDE, hass.config.longitude
        )
        self._location_name = location_name or config_entry.data.get(
            CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME
        )
        self._timezone = config_entry.data.get(
            CONF_TIMEZONE, str(hass.config.time_zone)
        )

        # Initialize provider
        self._provider: PrayerTimesProvider | None = None
        self._session: ClientSession | None = None

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(minutes=60),
        )

        LOGGER.debug(
            "Initialized coordinator for %s at (%s, %s)",
            self._location_name,
            self._latitude,
            self._longitude,
        )

    @property
    def latitude(self) -> float:
        """Return configured latitude."""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Return configured longitude."""
        return self._longitude

    @property
    def location_name(self) -> str:
        """Return configured location name."""
        return self._location_name

    @property
    def calc_method(self) -> str:
        """Return the calculation method."""
        return self.config_entry.options.get(
            CONF_CALC_METHOD,
            self.config_entry.data.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD),
        )

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return self.config_entry.data.get(CONF_SOURCE_TYPE, DEFAULT_SOURCE_TYPE)

    @property
    def iqamah_method(self) -> str:
        """Return the iqamah method."""
        return self.config_entry.options.get(CONF_IQAMAH_METHOD, DEFAULT_IQAMAH_METHOD)

    def _get_provider(self) -> PrayerTimesProvider:
        """Get or create the prayer times provider."""
        if self._provider is not None:
            return self._provider

        calc_method = self.calc_method
        source_type = self.source_type

        # Determine source type from calculation method if not explicitly set
        if source_type == DEFAULT_SOURCE_TYPE:
            if calc_method in IRELAND_CALC_METHODS.values():
                source_type = SOURCE_IRELAND

        # Get aiohttp session for API providers
        if self._session is None:
            self._session = async_get_clientsession(self.hass)

        config = ProviderConfig(
            latitude=self._latitude,
            longitude=self._longitude,
            calculation_method=calc_method,
            timezone=self._timezone,
        )

        if source_type == SOURCE_IRELAND:
            LOGGER.debug("Using Ireland provider for method: %s", calc_method)
            self._provider = IrelandProvider(config, self._session)
        else:
            LOGGER.debug("Using calculated provider for method: %s", calc_method)
            self._provider = CalculatedProvider(config, self._session)

        return self._provider

    def _get_iqamah_times_offset(
        self, prayer_times_dt: dict[str, datetime]
    ) -> dict[str, datetime]:
        """Compute iqamah times using offset values from configuration."""
        iqamah_offsets = self.config_entry.options.get(
            CONF_IQAMAH_OFFSETS, DEFAULT_IQAMAH_OFFSETS
        )
        iqamah = {}

        for prayer in PRAYERS:
            base_dt = prayer_times_dt.get(prayer)
            if base_dt:
                offset_minutes = iqamah_offsets.get(prayer, 0)
                iqamah_time = base_dt + timedelta(minutes=offset_minutes)
                iqamah[f"iqamah_{prayer}"] = iqamah_time

        return iqamah

    @callback
    def async_schedule_future_update(self, next_update_at: datetime) -> None:
        """Schedule the next update.

        Args:
            next_update_at: UTC datetime for next update.
        """
        LOGGER.debug(
            "Scheduling next update for %s at %s",
            self._location_name,
            next_update_at,
        )

        if self.event_unsub:
            self.event_unsub()

        self.event_unsub = async_track_point_in_time(
            self.hass, self.async_request_update, next_update_at
        )

    async def async_request_update(self, *_: Any) -> None:
        """Request an update from the coordinator."""
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update sensors with new prayer, iqamah and hijri date data."""
        LOGGER.debug("Starting prayer times update for %s", self._location_name)

        now = dt_util.now()
        today = date.today()
        provider = self._get_provider()

        try:
            # Fetch prayer times from provider
            prayer_data = await provider.async_fetch_prayer_times(today)
            LOGGER.debug(
                "Raw prayer times from provider: Fajr=%s, Maghrib=%s",
                prayer_data.fajr,
                prayer_data.maghrib,
            )

            # Fetch iqamah times if provider supports it
            iqamah_data = None
            if provider.supports_iqamah:
                iqamah_data = await provider.async_fetch_iqamah_times(today)

        except (ProviderConnectionError, ProviderResponseError) as err:
            LOGGER.warning(
                "Failed to fetch prayer times for %s: %s. Will retry in 60 seconds.",
                self._location_name,
                err,
            )
            raise UpdateFailed(f"Failed to fetch prayer times: {err}") from err

        except ProviderValidationError as err:
            LOGGER.error(
                "Prayer times validation failed for %s: %s",
                self._location_name,
                err,
            )
            raise UpdateFailed(f"Invalid prayer times: {err}") from err

        # Convert to dictionary with HA-compatible keys
        prayer_times_dt = prayer_data.to_dict()

        # Adjust times if they have already passed (show next occurrence)
        now_utc = dt_util.utcnow()
        for key, prayer_time in prayer_times_dt.items():
            if isinstance(prayer_time, datetime) and prayer_time < now_utc:
                # Time has passed, add a day
                prayer_times_dt[key] = prayer_time + timedelta(days=1)

        # Get iqamah times
        if iqamah_data:
            iqamah_times = iqamah_data.to_dict()
        elif self.iqamah_method == "offset":
            iqamah_times = self._get_iqamah_times_offset(prayer_times_dt)
        else:
            iqamah_times = {}

        # Get Hijri date
        hijri_date = await self.hass.async_add_executor_job(get_hijri_date, today)
        hijri_data = hijri_date.to_dict()

        # Determine next prayer
        next_prayer_name = None
        next_prayer_time = None
        for prayer in PRAYERS:
            prayer_time = prayer_times_dt.get(prayer)
            if prayer_time and prayer_time > now_utc:
                if next_prayer_time is None or prayer_time < next_prayer_time:
                    next_prayer_time = prayer_time
                    next_prayer_name = prayer

        # Build data dictionary
        data: dict[str, Any] = {}
        data.update(prayer_times_dt)
        data.update(iqamah_times)
        data.update(hijri_data)

        # Next prayer info
        if next_prayer_time:
            data["next_prayer"] = next_prayer_time
            data["next_prayer_name"] = next_prayer_name

            # Countdown sensors
            time_until = next_prayer_time - now_utc
            minutes_until = int(time_until.total_seconds() / 60)
            data["next_prayer_minutes"] = minutes_until
            data["next_prayer_countdown"] = (
                f"{next_prayer_name} in {minutes_until} minute{'s' if minutes_until != 1 else ''}"
            )

        # Current prayer period
        data["current_prayer_period"] = self._get_current_prayer_period(
            prayer_times_dt, now_utc
        )

        # Qibla direction
        qibla = calculate_qibla_direction(self._latitude, self._longitude)
        data["qibla_direction"] = qibla

        # Location info
        data["location_name"] = self._location_name

        # Special date info
        data["is_ramadan"] = is_ramadan(today)
        data["is_friday"] = is_friday(today)

        special_night = get_special_night(today)
        data["special_night"] = special_night if special_night else ""

        # Friday prayer (Jumu'a) - if Friday, dhuhr is replaced by juma
        if is_friday(today):
            data["juma_time"] = prayer_times_dt.get("Dhuhr")

        # Schedule next update at midnight
        midnight = dt_util.start_of_local_day(now + timedelta(days=1))
        # Add a small offset to ensure we're past midnight
        next_update = midnight + timedelta(minutes=1)
        self.async_schedule_future_update(next_update)

        LOGGER.info(
            "Prayer times updated for %s. Next prayer: %s at %s",
            self._location_name,
            next_prayer_name,
            next_prayer_time,
        )

        return data

    def _get_current_prayer_period(
        self, prayer_times: dict[str, datetime], now: datetime
    ) -> str:
        """Determine the current prayer period.

        Args:
            prayer_times: Dictionary of prayer times.
            now: Current UTC datetime.

        Returns:
            String describing the current period.
        """
        ordered_prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]

        for i, prayer in enumerate(ordered_prayers):
            prayer_time = prayer_times.get(prayer)
            if prayer_time and now < prayer_time:
                if i == 0:
                    return "Before Fajr"
                else:
                    prev_prayer = ordered_prayers[i - 1]
                    return f"Between {prev_prayer} and {prayer}"

        return "After Isha"

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self.event_unsub:
            self.event_unsub()
            self.event_unsub = None

        # Close provider session if needed
        if hasattr(self._provider, "close"):
            await self._provider.close()
