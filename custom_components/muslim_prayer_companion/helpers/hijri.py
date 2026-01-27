"""Hijri date utilities for Muslim Prayer Companion."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from hijri_converter import Gregorian, Hijri

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


@dataclass
class HijriDate:
    """Hijri date representation."""

    day: int
    month: int
    year: int
    month_name: str

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


def get_hijri_date(gregorian_date: date | None = None) -> HijriDate:
    """Convert a Gregorian date to Hijri date.

    Args:
        gregorian_date: The Gregorian date to convert. Defaults to today.

    Returns:
        HijriDate object with all date components.
    """
    if gregorian_date is None:
        gregorian_date = date.today()

    try:
        hijri = Gregorian(
            gregorian_date.year,
            gregorian_date.month,
            gregorian_date.day,
        ).to_hijri()

        month_name = HIJRI_MONTHS.get(hijri.month, f"Month {hijri.month}")

        return HijriDate(
            day=hijri.day,
            month=hijri.month,
            year=hijri.year,
            month_name=month_name,
        )
    except Exception as err:
        LOGGER.error("Failed to convert Gregorian date to Hijri: %s", err)
        # Return a fallback
        return HijriDate(
            day=1,
            month=1,
            year=1446,
            month_name="Muharram",
        )


def hijri_to_gregorian(hijri_year: int, hijri_month: int, hijri_day: int) -> date:
    """Convert Hijri date to Gregorian date.

    Args:
        hijri_year: Hijri year.
        hijri_month: Hijri month (1-12).
        hijri_day: Hijri day.

    Returns:
        Gregorian date.
    """
    gregorian = Hijri(hijri_year, hijri_month, hijri_day).to_gregorian()
    return date(gregorian.year, gregorian.month, gregorian.day)
