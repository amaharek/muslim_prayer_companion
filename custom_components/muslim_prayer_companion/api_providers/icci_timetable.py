"""
Bundled perpetual prayer timetable of the Islamic Cultural Centre of Ireland.

ICCI used to publish its timetable as JSON at https://islamireland.ie/api/timetable/.
That endpoint now serves the website's HTML, so the integration ships the last
published copy (see ``data/icci_timetable.json`` and ``scripts/build_icci_timetable.py``).

The table is keyed by month then day ("1".."12", "1".."31", with 29 February)
and holds six ``[hour, minute]`` pairs per day: fajr, shurooq (sunrise), dhuhr,
asr, maghrib and isha, in Irish clock time. The table switches clocks on
1 April and 1 November instead of the real DST dates, so a day's times are on
UTC+1 for April to October and on UTC+0 otherwise, whatever the real clock does.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from functools import cache
import json
import logging
from pathlib import Path

from .base import PrayerTimesData, ProviderResult, midpoint

LOGGER = logging.getLogger(__name__)

ICCI_TIMETABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "icci_timetable.json"
ICCI_SOURCE_ID = "icci-timetable"
# Months whose rows are on summer time (UTC+1): April to October inclusive.
ICCI_SUMMER_MONTHS = range(4, 11)
PRAYERS_PER_DAY = 6
HOURS_PER_DAY = 24
MINUTES_PER_HOUR = 60
# A leap year, so every month gets its full day count (29 February included).
LEAP_YEAR = 2024

Timetable = dict[str, dict[str, list[list[int]]]]


def is_valid_icci_day(prayers: object) -> bool:
    """Check one timetable day: six ``[hour, minute]`` pairs of ints in range."""
    return (
        isinstance(prayers, list)
        and len(prayers) == PRAYERS_PER_DAY
        and all(
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(value, int) and not isinstance(value, bool) for value in pair)
            and 0 <= pair[0] < HOURS_PER_DAY
            and 0 <= pair[1] < MINUTES_PER_HOUR
            for pair in prayers
        )
    )


def validate_timetable(timetable: object) -> Timetable:
    """
    Return ``timetable`` if every day of a leap year is present and well formed.

    Raises:
        TypeError: If the timetable or a month is not an object.
        ValueError: If a day is missing or malformed.
    """
    if not isinstance(timetable, dict):
        msg = "timetable is not an object"
        raise TypeError(msg)
    for month in range(1, 13):
        days = timetable.get(str(month))
        if not isinstance(days, dict):
            msg = f"month {month} is missing"
            raise TypeError(msg)
        for day in range(1, calendar.monthrange(LEAP_YEAR, month)[1] + 1):
            if not is_valid_icci_day(days.get(str(day))):
                msg = f"invalid prayer times for {day}/{month}"
                raise ValueError(msg)
    return timetable


@cache
def load_icci_timetable() -> Timetable | None:
    """
    Load and validate the bundled timetable once per process.

    This reads a file: call it from executor code, never from the event loop.
    The result (including ``None``) is cached, so a missing or corrupt file is
    reported with a single warning per run.
    """
    path = ICCI_TIMETABLE_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        timetable = validate_timetable(data["timetable"])
    except (OSError, ValueError, KeyError, TypeError) as err:
        LOGGER.warning(
            "ICCI timetable %s is missing or corrupt (%s); "
            "ICCI prayer times will fall back to the calculated method",
            path,
            err,
        )
        return None
    return timetable


def icci_table_utc_offset(day: date) -> timedelta:
    """Return the UTC offset the timetable's clock uses for ``day``."""
    return timedelta(hours=1) if day.month in ICCI_SUMMER_MONTHS else timedelta(0)


def icci_row_to_utc(day: date, clock: list[int]) -> datetime:
    """Convert a timetable ``[hour, minute]`` on ``day`` to a UTC datetime."""
    naive_utc = datetime(day.year, day.month, day.day, clock[0], clock[1], tzinfo=UTC)
    return naive_utc - icci_table_utc_offset(day)


def icci_day_times(timetable: Timetable, day: date) -> PrayerTimesData:
    """Return the six prayer times of ``day`` as UTC datetimes (no Midnight yet)."""
    row = timetable[str(day.month)][str(day.day)]
    fajr, sunrise, dhuhr, asr, maghrib, isha = (icci_row_to_utc(day, clock) for clock in row)
    return PrayerTimesData(
        fajr=fajr,
        sunrise=sunrise,
        dhuhr=dhuhr,
        asr=asr,
        maghrib=maghrib,
        isha=isha,
        sunset=maghrib,
        source=ICCI_SOURCE_ID,
    )


def build_icci_result(timetable: Timetable, day: date) -> ProviderResult:
    """Return today's and tomorrow's times, with Midnight as the Maghrib-sunrise midpoint."""
    today = icci_day_times(timetable, day)
    tomorrow = icci_day_times(timetable, day + timedelta(days=1))
    day_after = icci_day_times(timetable, day + timedelta(days=2))
    today.midnight = midpoint(today.maghrib, tomorrow.sunrise)
    tomorrow.midnight = midpoint(tomorrow.maghrib, day_after.sunrise)
    return ProviderResult(today=today, tomorrow=tomorrow, source=ICCI_SOURCE_ID)
