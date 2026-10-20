"""
Hijri date utilities for Muslim Prayer Companion.

Dates come from ``hijridate`` (the Umm al-Qura calendar, valid from 1924-08-01
to 2077-11-16). Two user options are applied on top: a day adjustment of up to
two days either way, to follow local moon sighting, and whether the Hijri day
changes at Maghrib (as it does religiously) or at midnight.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import cache
import logging
from typing import TYPE_CHECKING

from hijridate import Gregorian, Hijri

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)

# Month names in English
HIJRI_MONTHS = {
    1: "Muharram",
    2: "Safar",
    3: "Rabi al-Awwal",
    4: "Rabi al-Thani",
    5: "Jumada al-Awwal",
    6: "Jumada al-Thani",
    7: "Rajab",
    8: "Sha'ban",
    9: "Ramadan",
    10: "Shawwal",
    11: "Dhul Qi'dah",
    12: "Dhul Hijjah",
}
RAMADAN = 9


@dataclass(frozen=True)
class HijriDate:
    """Hijri date representation."""

    day: int
    month: int
    year: int
    month_name: str
    month_length: int = 30

    @property
    def date_string(self) -> str:
        """Return date in DD-MM-YYYY format."""
        return f"{self.day:02d}-{self.month:02d}-{self.year}"

    @property
    def readable_date(self) -> str:
        """Return human-readable date string."""
        return f"{self.day}-{self.month_name}-{self.year}"

    @property
    def day_month_readable(self) -> str:
        """Return day and month readable string."""
        return f"{self.day}-{self.month_name}"

    def to_dict(self) -> dict[str, str | int]:
        """Convert to dictionary for sensor data."""
        return {
            "hijri_date": self.date_string,
            "hijri_day": str(self.day),
            "hijri_month_num": self.month,
            "hijri_month_readable": self.month_name,
            "hijri_year": str(self.year),
            "hijri_date_readable": self.readable_date,
            "hijri_day_month_readable": self.day_month_readable,
        }


@cache
def _warn_once(message: str) -> None:
    """Log a warning the first time ``message`` is seen in this process."""
    LOGGER.warning("%s", message)


def get_hijri_date(gregorian_date: date, adjustment_days: int = 0) -> HijriDate | None:
    """
    Convert a Gregorian date to the Hijri date, shifted by ``adjustment_days``.

    Returns None (and warns once) when the date is outside the calendar's range.
    """
    base = gregorian_date + timedelta(days=adjustment_days)
    try:
        hijri = Gregorian(base.year, base.month, base.day).to_hijri()
    except (OverflowError, ValueError) as err:
        _warn_once(f"Cannot convert {base} to a Hijri date: {err}")
        return None
    return HijriDate(
        day=hijri.day,
        month=hijri.month,
        year=hijri.year,
        month_name=HIJRI_MONTHS.get(hijri.month, f"Month {hijri.month}"),
        month_length=hijri.month_length(),
    )


def effective_hijri_date(
    now_utc: datetime,
    local_tz: ZoneInfo,
    maghrib_today_utc: datetime | None,
    *,
    change_at_maghrib: bool = False,
    adjustment_days: int = 0,
) -> HijriDate | None:
    """
    Return the Hijri date in force at ``now_utc``.

    With ``change_at_maghrib`` the Hijri day advances at today's Maghrib
    instead of at local midnight.
    """
    base = now_utc.astimezone(local_tz).date()
    if change_at_maghrib and maghrib_today_utc is not None and now_utc >= maghrib_today_utc:
        base += timedelta(days=1)
    return get_hijri_date(base, adjustment_days)


def hijri_to_gregorian(
    hijri_year: int, hijri_month: int, hijri_day: int, adjustment_days: int = 0
) -> date | None:
    """
    Convert a Hijri date to the Gregorian date it falls on.

    ``adjustment_days`` is the user's Hijri adjustment: with an adjustment of
    +1 the Hijri date is one day ahead of Umm al-Qura, so each Hijri date falls
    one Gregorian day earlier.
    """
    try:
        gregorian = Hijri(hijri_year, hijri_month, hijri_day).to_gregorian()
    except (OverflowError, ValueError):
        return None
    return date(gregorian.year, gregorian.month, gregorian.day) - timedelta(days=adjustment_days)
