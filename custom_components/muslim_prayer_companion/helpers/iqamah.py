"""Iqamah (congregation) times: offsets, mosque-published, or a custom JSON API."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from typing import TYPE_CHECKING, Any

from ..api_providers.base import IqamahTimesData, ProviderError, local_clock_to_utc
from ..api_providers.dpt import DPT_JAMAH_KEYS, parse_clock
from ..api_providers.http import fetch_json
from ..const import PRAYERS

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from aiohttp import ClientSession

LOGGER = logging.getLogger(__name__)


def iqamah_from_offsets(
    prayer_times: dict[str, datetime], offsets: dict[str, int]
) -> dict[str, datetime]:
    """Return ``{prayer: time + offset}`` for the five prayers present in ``prayer_times``."""
    result: dict[str, datetime] = {}
    for prayer in PRAYERS:
        base = prayer_times.get(prayer)
        if base is not None:
            result[prayer] = base + timedelta(minutes=int(offsets.get(prayer, 0)))
    return result


def parse_iqamah_json(payload: Any, target_date: date, tz: ZoneInfo) -> IqamahTimesData:
    """
    Parse a custom iqamah JSON document.

    Accepted shapes: the dpt ``*_jamah`` keys, ``{"Fajr": "HH:MM", ...}``
    (case-insensitive prayer names), or either of those under an ``"iqamah"`` key.
    A one-element list is unwrapped.

    Raises:
        ValueError: If no iqamah time could be read.
    """
    if isinstance(payload, list):
        if not payload:
            msg = "empty iqamah response"
            raise ValueError(msg)
        payload = payload[0]
    if not isinstance(payload, dict):
        msg = f"unexpected iqamah payload type {type(payload).__name__}"
        raise TypeError(msg)
    if isinstance(payload.get("iqamah"), dict):
        payload = payload["iqamah"]

    lowered = {str(key).lower(): value for key, value in payload.items()}
    values: dict[str, datetime | None] = {}
    for prayer in PRAYERS:
        name = prayer.lower()
        raw = lowered.get(DPT_JAMAH_KEYS[name], lowered.get(name))
        clock: time | None = parse_clock(raw)
        values[name] = (
            local_clock_to_utc(target_date, clock.hour, clock.minute, tz) if clock else None
        )

    if all(value is None for value in values.values()):
        msg = "no iqamah times found in response"
        raise ValueError(msg)
    return IqamahTimesData(**values)


class IqamahApiClient:
    """Fetch iqamah times from a user-supplied JSON URL, keeping the last good value."""

    def __init__(self, session: ClientSession | None, url: str, tz: ZoneInfo) -> None:
        """Initialize the client."""
        self._session = session
        self._url = url
        self._tz = tz
        self._last_good: tuple[date, IqamahTimesData] | None = None
        self._failing = False

    @property
    def url(self) -> str:
        """Return the configured URL."""
        return self._url

    async def async_fetch(self, target_date: date) -> IqamahTimesData | None:
        """Return today's iqamah times, or the last good ones, or None."""
        try:
            payload = await fetch_json(self._session, self._url)
            data = parse_iqamah_json(payload, target_date, self._tz)
        except (ProviderError, TypeError, ValueError) as err:
            if not self._failing:
                LOGGER.warning("Could not fetch iqamah times from %s: %s", self._url, err)
                self._failing = True
            if self._last_good and self._last_good[0] == target_date:
                return self._last_good[1]
            return None
        if self._failing:
            LOGGER.info("Iqamah times from %s are available again", self._url)
            self._failing = False
        self._last_good = (target_date, data)
        return data
