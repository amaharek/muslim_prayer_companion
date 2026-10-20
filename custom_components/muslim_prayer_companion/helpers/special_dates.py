"""
Special Islamic date utilities.

All functions take an already computed :class:`HijriDate` (see
``hijri.effective_hijri_date``) so that the user's adjustment and the
Maghrib rollover are applied consistently everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .hijri import RAMADAN, HijriDate, hijri_to_gregorian

if TYPE_CHECKING:
    from datetime import date

FRIDAY = 4
LAST_TEN_NIGHTS_START = 21
EID_AL_FITR_DAYS = (1, 2, 3)
EID_AL_ADHA_DAYS = (10, 11, 12, 13)

# (month, day, name) of the events the "upcoming event" sensor tracks.
ISLAMIC_EVENTS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Islamic New Year"),
    (1, 10, "Day of Ashura"),
    (3, 12, "Mawlid an-Nabi"),
    (7, 27, "Laylatul Mi'raj"),
    (8, 15, "Laylatul Bara'ah"),
    (9, 1, "First day of Ramadan"),
    (9, 27, "Laylatul Qadr (27th night)"),
    (10, 1, "Eid al-Fitr"),
    (12, 9, "Day of Arafah"),
    (12, 10, "Eid al-Adha"),
)


@dataclass(frozen=True)
class IslamicEvent:
    """An upcoming event with its Gregorian date."""

    name: str
    date: date
    days_until: int


def is_friday(local_date: date) -> bool:
    """Return True if ``local_date`` is a Friday (Jumu'ah)."""
    return local_date.weekday() == FRIDAY


def is_ramadan(hijri: HijriDate | None) -> bool:
    """Return True if the Hijri date is in Ramadan."""
    return hijri is not None and hijri.month == RAMADAN


def ramadan_day(hijri: HijriDate | None) -> int | None:
    """Return the day of Ramadan (1-30), or None outside Ramadan."""
    return hijri.day if is_ramadan(hijri) else None


def get_special_night(hijri: HijriDate | None) -> str | None:
    """Return the name of the special night that starts on this Hijri date, if any."""
    if hijri is None:
        return None

    # The night before Eid al-Fitr is the last night of Ramadan (29 or 30 days).
    if hijri.month == RAMADAN and hijri.day == hijri.month_length:
        return "Night before Eid al-Fitr"

    # Laylatul Qadr: odd nights of the last ten nights of Ramadan.
    if hijri.month == RAMADAN and hijri.day >= LAST_TEN_NIGHTS_START and hijri.day % 2 == 1:
        return f"Possible Laylatul Qadr (Night {hijri.day})"

    if hijri.month == 12 and hijri.day == 9:
        return "Night of Arafah"

    if hijri.month == 8 and hijri.day == 15:
        return "Laylatul Bara'ah (Night of Forgiveness)"

    if hijri.month == 7 and hijri.day == 27:
        return "Laylatul Mi'raj (Night Journey)"

    if hijri.month == 1 and hijri.day == 9:
        return "Night before Ashura"

    return None


def is_eid(hijri: HijriDate | None) -> str | None:
    """Return "Eid al-Fitr", "Eid al-Adha" or None."""
    if hijri is None:
        return None
    if hijri.month == 10 and hijri.day in EID_AL_FITR_DAYS:
        return "Eid al-Fitr"
    if hijri.month == 12 and hijri.day in EID_AL_ADHA_DAYS:
        return "Eid al-Adha"
    return None


def days_until_ramadan(
    hijri: HijriDate | None, today: date, adjustment_days: int = 0
) -> int | None:
    """Return the days until the next 1 Ramadan, or None during Ramadan."""
    if hijri is None or hijri.month == RAMADAN:
        return None
    year = hijri.year if hijri.month < RAMADAN else hijri.year + 1
    first = hijri_to_gregorian(year, RAMADAN, 1, adjustment_days)
    if first is None:
        return None
    return max((first - today).days, 0)


def upcoming_islamic_event(
    hijri: HijriDate | None, today: date, adjustment_days: int = 0
) -> IslamicEvent | None:
    """Return the next event from ISLAMIC_EVENTS on or after ``today``."""
    if hijri is None:
        return None
    best: IslamicEvent | None = None
    for year in (hijri.year, hijri.year + 1):
        for month, day, name in ISLAMIC_EVENTS:
            event_date = hijri_to_gregorian(year, month, day, adjustment_days)
            if event_date is None:
                continue
            days = (event_date - today).days
            if days < 0:
                continue
            if best is None or days < best.days_until:
                best = IslamicEvent(name=name, date=event_date, days_until=days)
    return best
