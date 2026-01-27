"""Special Islamic date utilities."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from .hijri import HijriDate, get_hijri_date


def is_ramadan(gregorian_date: date | None = None) -> bool:
    """Check if the given date falls in Ramadan.

    Args:
        gregorian_date: The date to check. Defaults to today.

    Returns:
        True if the date is in Ramadan (month 9).
    """
    hijri = get_hijri_date(gregorian_date)
    return hijri.month == 9


def is_friday(gregorian_date: date | None = None) -> bool:
    """Check if the given date is Friday (Jumu'a).

    Args:
        gregorian_date: The date to check. Defaults to today.

    Returns:
        True if the date is Friday.
    """
    if gregorian_date is None:
        gregorian_date = date.today()
    return gregorian_date.weekday() == 4  # Friday is weekday 4


def get_special_night(gregorian_date: date | None = None) -> str | None:
    """Detect if the given night is a special Islamic night.

    Args:
        gregorian_date: The date to check. Defaults to today.

    Returns:
        Name of the special night, or None if not special.
    """
    hijri = get_hijri_date(gregorian_date)

    # Check for Laylatul Qadr (last 10 nights of Ramadan, odd nights)
    if hijri.month == 9 and hijri.day >= 21:
        if hijri.day in (21, 23, 25, 27, 29):
            return f"Possible Laylatul Qadr (Night {hijri.day})"

    # Night before Eid al-Fitr (1st of Shawwal)
    if hijri.month == 9 and hijri.day == 29:
        return "Night before Eid al-Fitr"

    # Night before Eid al-Adha (10th of Dhul Hijjah)
    if hijri.month == 12 and hijri.day == 9:
        return "Night of Arafah"

    # Laylatul Bara'ah (15th of Sha'ban)
    if hijri.month == 8 and hijri.day == 15:
        return "Laylatul Bara'ah (Night of Forgiveness)"

    # Laylatul Mi'raj (27th of Rajab)
    if hijri.month == 7 and hijri.day == 27:
        return "Laylatul Mi'raj (Night Journey)"

    # Laylatul Isra (27th of Rajab - same as Mi'raj)
    # Already covered above

    # Night of Ashura (10th of Muharram)
    if hijri.month == 1 and hijri.day == 9:
        return "Night before Ashura"

    return None


def get_upcoming_islamic_event(
    gregorian_date: date | None = None, days_ahead: int = 30
) -> dict[str, str | date] | None:
    """Get the next upcoming Islamic event within the specified days.

    Args:
        gregorian_date: Starting date. Defaults to today.
        days_ahead: Number of days to look ahead.

    Returns:
        Dictionary with event name and date, or None if no event found.
    """
    if gregorian_date is None:
        gregorian_date = date.today()

    # Define important Islamic events by Hijri month and day
    events = [
        (1, 1, "Islamic New Year"),
        (1, 10, "Day of Ashura"),
        (3, 12, "Mawlid an-Nabi (Prophet's Birthday)"),
        (7, 27, "Laylatul Mi'raj"),
        (8, 15, "Laylatul Bara'ah"),
        (9, 1, "First day of Ramadan"),
        (9, 27, "Laylatul Qadr (most likely)"),
        (10, 1, "Eid al-Fitr"),
        (12, 9, "Day of Arafah"),
        (12, 10, "Eid al-Adha"),
    ]

    closest_event = None
    closest_days = days_ahead + 1

    for day_offset in range(days_ahead + 1):
        check_date = gregorian_date + timedelta(days=day_offset)
        hijri = get_hijri_date(check_date)

        for month, day, event_name in events:
            if hijri.month == month and hijri.day == day:
                if day_offset < closest_days:
                    closest_days = day_offset
                    closest_event = {
                        "name": event_name,
                        "date": check_date,
                        "days_until": day_offset,
                        "hijri_date": hijri.readable_date,
                    }

    return closest_event


def is_eid(gregorian_date: date | None = None) -> str | None:
    """Check if the given date is Eid.

    Args:
        gregorian_date: The date to check. Defaults to today.

    Returns:
        "Eid al-Fitr", "Eid al-Adha", or None.
    """
    hijri = get_hijri_date(gregorian_date)

    # Eid al-Fitr: 1st of Shawwal (can extend to 3 days)
    if hijri.month == 10 and hijri.day in (1, 2, 3):
        return "Eid al-Fitr"

    # Eid al-Adha: 10th-13th of Dhul Hijjah
    if hijri.month == 12 and hijri.day in (10, 11, 12, 13):
        return "Eid al-Adha"

    return None


def days_until_ramadan(gregorian_date: date | None = None) -> int | None:
    """Calculate days until the next Ramadan.

    Args:
        gregorian_date: Starting date. Defaults to today.

    Returns:
        Number of days until Ramadan, or None if already in Ramadan.
    """
    if gregorian_date is None:
        gregorian_date = date.today()

    hijri = get_hijri_date(gregorian_date)

    # If already in Ramadan
    if hijri.month == 9:
        return None

    # Calculate days until month 9
    # This is an approximation - actual calculation would need full calendar
    if hijri.month < 9:
        months_until = 9 - hijri.month
    else:
        months_until = (12 - hijri.month) + 9

    # Approximate days (29.5 days per lunar month on average)
    approximate_days = int(months_until * 29.5) - hijri.day + 1

    return max(0, approximate_days)
