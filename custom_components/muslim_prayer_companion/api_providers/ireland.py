"""
Unified provider for the Irish mosques listed in ``data/mosques.json``.

One provider class serves every registry source type:

* ``icci_timetable``: the bundled ICCI perpetual timetable (offline),
* ``dpt``: the WordPress "Daily Prayer Time" plugin JSON API (MCND, HICC, SDIC),
* ``mai_html``: the Muslim Association of Ireland homepage (Tallaght).

Network payloads are cached for a few minutes so prayer times, iqamah times
and Friday prayers share a single request per refresh.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
import logging
import time as time_module
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from ..const import PAYLOAD_CACHE_SECONDS
from ..helpers.registry import (
    MOSQUE_KEYS,
    SOURCE_TYPE_DPT,
    SOURCE_TYPE_ICCI_TIMETABLE,
    SOURCE_TYPE_MAI_HTML,
    Mosque,
    get_mosque,
    mosques_by_distance,
)
from .base import (
    IqamahTimesData,
    MosqueInfo,
    PrayerTimesData,
    PrayerTimesProvider,
    ProviderConfig,
    ProviderResponseError,
    ProviderResult,
    ProviderValidationError,
)
from .dpt import parse_dpt_payload
from .http import fetch_json, fetch_text
from .icci_timetable import build_icci_result, load_icci_timetable
from .mai import build_mai_result, parse_mai_homepage

if TYPE_CHECKING:
    from aiohttp import ClientSession

LOGGER = logging.getLogger(__name__)


def mosque_info(mosque: Mosque) -> MosqueInfo:
    """Return the provider-layer MosqueInfo for a registry record."""
    return MosqueInfo(
        name=mosque.name,
        uuid=mosque.key,
        latitude=mosque.latitude,
        longitude=mosque.longitude,
        address=mosque.address,
        city=mosque.city,
        country=mosque.country,
        website=mosque.website,
        timezone=mosque.timezone,
        short_name=mosque.short_name,
    )


class IrelandProvider(PrayerTimesProvider):
    """Prayer times from an Irish mosque's published source."""

    name = "ireland"

    def __init__(self, config: ProviderConfig, session: ClientSession | None = None) -> None:
        """
        Initialize the provider for the mosque named by ``calculation_method``.

        Raises:
            ValueError: If the mosque key is not in the registry.
        """
        super().__init__(config, session)

        key = config.calculation_method.lower()
        try:
            self.mosque = get_mosque(key)
        except KeyError:
            msg = f"Unknown Ireland API: {key}. Valid options: {', '.join(MOSQUE_KEYS)}"
            raise ValueError(msg) from None
        self._key = key
        self.source_id = self.mosque.source_id
        self._tz = ZoneInfo(self.mosque.timezone)
        # (date the payload is for, monotonic fetch time, payload)
        self._payload: tuple[date, float, Any] | None = None

    @property
    def key(self) -> str:
        """Return the registry key, e.g. ``ie-icci``."""
        return self._key

    @property
    def api_name(self) -> str:
        """Return the mosque name."""
        return self.mosque.name

    @property
    def url(self) -> str:
        """Return the URL the data comes from, or the website for bundled data."""
        return self.mosque.source.url or self.mosque.website

    @property
    def mosque_info(self) -> MosqueInfo:
        """Return mosque information."""
        return mosque_info(self.mosque)

    @property
    def timezone(self) -> ZoneInfo:
        """Return the mosque's time zone."""
        return self._tz

    # --- HTTP -----------------------------------------------------------------

    async def _fetch_text(self, url: str) -> str:
        """GET ``url`` and return the body as text (see ``http.fetch_text``)."""
        return await fetch_text(self._session, url)

    async def _fetch_json(self, url: str) -> Any:
        """GET ``url`` and parse the body as JSON (see ``http.fetch_json``)."""
        return await fetch_json(self._session, url)

    async def async_get_payload(self, target_date: date) -> Any:
        """Return the raw payload for ``target_date``, fetching at most every few minutes."""
        now = time_module.monotonic()
        if (
            self._payload is not None
            and self._payload[0] == target_date
            and now - self._payload[1] < PAYLOAD_CACHE_SECONDS
        ):
            return self._payload[2]

        source = self.mosque.source
        if source.type == SOURCE_TYPE_DPT:
            payload = await self._fetch_json(source.url or "")
        elif source.type == SOURCE_TYPE_MAI_HTML:
            payload = await self._fetch_text(source.url or "")
        else:
            msg = f"{self.api_name} has no network payload"
            raise ProviderResponseError(msg)
        self._payload = (target_date, now, payload)
        return payload

    def clear_cache(self) -> None:
        """Forget the cached payload."""
        self._payload = None

    # --- Fetching -------------------------------------------------------------

    async def async_fetch(self, target_date: date) -> ProviderResult:
        """Fetch everything the mosque publishes for ``target_date``."""
        source_type = self.mosque.source.type
        if source_type == SOURCE_TYPE_ICCI_TIMETABLE:
            result = await self._fetch_icci(target_date)
        elif source_type == SOURCE_TYPE_DPT:
            result = await self._fetch_dpt(target_date)
        elif source_type == SOURCE_TYPE_MAI_HTML:
            result = await self._fetch_mai(target_date)
        else:  # pragma: no cover - the registry validates source types
            msg = f"Unsupported source type {source_type!r}"
            raise ProviderResponseError(msg)

        for data in (result.today, result.tomorrow):
            if data is None:
                continue
            try:
                data.validate()
            except AssertionError as err:
                msg = f"Invalid prayer times from {self.api_name}: {err}"
                raise ProviderValidationError(msg) from err
        return result

    async def _fetch_icci(self, target_date: date) -> ProviderResult:
        """Read the bundled ICCI timetable (file I/O off the event loop)."""
        timetable = await asyncio.to_thread(load_icci_timetable)
        if timetable is None:
            msg = "Bundled ICCI timetable is missing or corrupt"
            raise ProviderResponseError(msg)
        return build_icci_result(timetable, target_date)

    async def _fetch_dpt(self, target_date: date) -> ProviderResult:
        """Fetch and parse the WordPress dpt payload."""
        payload = await self.async_get_payload(target_date)
        try:
            return parse_dpt_payload(payload, target_date, self._tz, self.source_id)
        except (KeyError, ValueError, TypeError) as err:
            msg = f"Invalid response from {self.api_name}: {err}"
            raise ProviderResponseError(msg) from err

    async def _fetch_mai(self, target_date: date) -> ProviderResult:
        """Fetch and parse the MAI homepage (today only, Dublin date)."""
        dublin_today = datetime.now(UTC).astimezone(self._tz).date()
        if target_date != dublin_today:
            msg = f"{self.api_name} only publishes today's times ({dublin_today})"
            raise ProviderResponseError(msg)
        html = await self.async_get_payload(target_date)
        try:
            parsed = parse_mai_homepage(html)
        except ValueError as err:
            msg = f"Could not read prayer times from {self.url}: {err}"
            raise ProviderResponseError(msg) from err
        return build_mai_result(parsed, dublin_today, self._tz)

    async def async_fetch_prayer_times(self, target_date: date) -> PrayerTimesData:
        """Fetch prayer times for one date."""
        return (await self.async_fetch(target_date)).today

    async def async_fetch_iqamah_times(self, target_date: date) -> IqamahTimesData | None:
        """Fetch iqamah times; only dpt mosques publish them."""
        if not self.supports_iqamah:
            return None
        return (await self.async_fetch(target_date)).iqamah

    # --- Capabilities ---------------------------------------------------------

    async def async_search_mosques(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10,  # noqa: ARG002 - interface argument, the registry is small
    ) -> list[MosqueInfo]:
        """Return every registered mosque, nearest to the given point first."""
        return [mosque_info(m) for m, _ in mosques_by_distance(latitude, longitude)]

    @property
    def supports_iqamah(self) -> bool:
        """Dpt mosques publish jamah (iqamah) times."""
        return self.mosque.supports_iqamah

    @property
    def supports_jumuah(self) -> bool:
        """Return True if the mosque publishes its Jumu'ah times."""
        return self.mosque.jumuah_auto

    @property
    def supports_mosque_search(self) -> bool:
        """The registry can be listed."""
        return True

    @property
    def supports_any_date(self) -> bool:
        """Only the bundled timetable covers arbitrary dates."""
        return self.mosque.supports_any_date
