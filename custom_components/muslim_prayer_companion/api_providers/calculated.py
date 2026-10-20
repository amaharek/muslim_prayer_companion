"""
Calculated prayer times provider using prayer-times-calculator-offline.

The library is the one Home Assistant's core ``islamic_prayer_times``
integration uses: it computes everything locally (no network) and, with
``iso8601=True``, returns timezone-aware ISO strings in UTC.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta
import logging
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from prayer_times_calculator_offline import PrayerTimesCalculator

from ..const import DEFAULT_CALC_METHOD, STANDARD_CALC_METHODS
from .base import (
    PrayerTimesData,
    PrayerTimesProvider,
    ProviderConfig,
    ProviderResponseError,
    ProviderResult,
    ProviderValidationError,
    ensure_after,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

LOGGER = logging.getLogger(__name__)

MIN_TIME_PARTS = 2


def parse_calculated_time(value: Any, target_date: date, tz: ZoneInfo) -> datetime:
    """
    Parse one value from the calculator into a UTC datetime.

    Accepts an ISO 8601 string with an offset (the ``iso8601=True`` output) or a
    bare ``"HH:MM"`` wall-clock string in ``tz``.
    """
    if not isinstance(value, str) or not value:
        msg = f"expected a time string, got {value!r}"
        raise ValueError(msg)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parts = value.split(":")
        if len(parts) < MIN_TIME_PARTS:
            msg = f"invalid time {value!r}"
            raise ValueError(msg) from None
        clock = time(int(parts[0]), int(parts[1]))
        return datetime.combine(target_date, clock, tzinfo=tz).astimezone(UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(UTC)


def parse_calculated_times(
    raw: dict[str, Any], target_date: date, tz: ZoneInfo, source: str
) -> PrayerTimesData:
    """Parse the calculator's result dictionary into PrayerTimesData."""
    maghrib = parse_calculated_time(raw["Maghrib"], target_date, tz)
    data = PrayerTimesData(
        fajr=parse_calculated_time(raw["Fajr"], target_date, tz),
        sunrise=parse_calculated_time(raw["Sunrise"], target_date, tz),
        dhuhr=parse_calculated_time(raw["Dhuhr"], target_date, tz),
        asr=parse_calculated_time(raw["Asr"], target_date, tz),
        maghrib=maghrib,
        isha=ensure_after(parse_calculated_time(raw["Isha"], target_date, tz), maghrib),
        source=source,
    )
    if raw.get("Sunset"):
        data.sunset = parse_calculated_time(raw["Sunset"], target_date, tz)
    if raw.get("Midnight"):
        data.midnight = ensure_after(
            parse_calculated_time(raw["Midnight"], target_date, tz), maghrib
        )
    return data


class CalculatedProvider(PrayerTimesProvider):
    """Provider that calculates prayer times locally."""

    name = "calculated"

    def __init__(self, config: ProviderConfig, session: ClientSession | None = None) -> None:
        """
        Initialize the calculated provider.

        Args:
            config: Provider configuration with latitude, longitude,
                calculation_method and timezone.
            session: Unused; accepted for interface compatibility.
        """
        super().__init__(config, session)

        method = config.calculation_method.lower()
        if method not in STANDARD_CALC_METHODS:
            LOGGER.warning(
                "Unknown calculation method '%s', defaulting to '%s'",
                config.calculation_method,
                DEFAULT_CALC_METHOD,
            )
            method = DEFAULT_CALC_METHOD
        self._method = method
        self.source_id = f"calculated:{method}"
        self.fallback_source_id = f"calculated-fallback:{method}"
        try:
            self._tz = ZoneInfo(config.timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            LOGGER.warning("Unknown time zone %r, using UTC", config.timezone)
            self._tz = ZoneInfo("UTC")

    @property
    def method(self) -> str:
        """Return the calculation method actually in use."""
        return self._method

    def _calculate(self, target_date: date) -> dict[str, Any]:
        """Run the calculator for one day (blocking, CPU only)."""
        calc = PrayerTimesCalculator(
            latitude=self.config.latitude,
            longitude=self.config.longitude,
            calculation_method=self._method,
            date=str(target_date),
            iso8601=True,
        )
        return calc.fetch_prayer_times()

    def _calculate_days(self, *days: date) -> list[dict[str, Any]]:
        """Run the calculator for several days in one executor hop."""
        return [self._calculate(day) for day in days]

    def _parse(self, raw: dict[str, Any], target_date: date) -> PrayerTimesData:
        """Parse and validate one day's raw result."""
        try:
            data = parse_calculated_times(raw, target_date, self._tz, self.source_id)
        except (KeyError, ValueError, TypeError) as err:
            msg = f"Invalid prayer times format: {err}"
            raise ProviderResponseError(msg) from err
        try:
            data.validate()
        except AssertionError as err:
            msg = f"Prayer times validation failed: {err}"
            raise ProviderValidationError(msg) from err
        return data

    async def async_fetch_prayer_times(self, target_date: date) -> PrayerTimesData:
        """Calculate prayer times for one date."""
        try:
            raw = await asyncio.to_thread(self._calculate, target_date)
        except Exception as err:
            msg = f"Prayer calculation failed: {err}"
            raise ProviderResponseError(msg) from err
        return self._parse(raw, target_date)

    async def async_fetch(self, target_date: date) -> ProviderResult:
        """Calculate today and tomorrow in a single executor hop."""
        tomorrow_date = target_date + timedelta(days=1)
        try:
            raw_today, raw_tomorrow = await asyncio.to_thread(
                self._calculate_days, target_date, tomorrow_date
            )
        except Exception as err:
            msg = f"Prayer calculation failed: {err}"
            raise ProviderResponseError(msg) from err
        return ProviderResult(
            today=self._parse(raw_today, target_date),
            tomorrow=self._parse(raw_tomorrow, tomorrow_date),
            source=self.source_id,
        )

    @property
    def supports_any_date(self) -> bool:
        """The calculator works for any date."""
        return True
