"""Tests for Ramadan, special nights and upcoming events."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.muslim_prayer_companion.helpers.hijri import (
    HijriDate,
    get_hijri_date,
    hijri_to_gregorian,
)
from custom_components.muslim_prayer_companion.helpers.special_dates import (
    days_until_ramadan,
    get_special_night,
    is_eid,
    is_friday,
    is_ramadan,
    ramadan_day,
    upcoming_islamic_event,
)


def hijri(day: int, month: int, year: int = 1447, length: int = 30) -> HijriDate:
    return HijriDate(day=day, month=month, year=year, month_name="x", month_length=length)


def test_is_friday() -> None:
    """20 Oct 2026 is a Tuesday, 23 Oct a Friday."""
    assert is_friday(date(2026, 10, 23)) is True
    assert is_friday(date(2026, 10, 20)) is False


def test_ramadan_helpers() -> None:
    """Ramadan detection and day number."""
    assert is_ramadan(hijri(12, 9)) is True
    assert ramadan_day(hijri(12, 9)) == 12
    assert is_ramadan(hijri(12, 8)) is False
    assert ramadan_day(hijri(12, 8)) is None
    assert is_ramadan(None) is False
    assert ramadan_day(None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (hijri(30, 9, length=30), "Night before Eid al-Fitr"),
        (hijri(29, 9, length=29), "Night before Eid al-Fitr"),
        (hijri(29, 9, length=30), "Possible Laylatul Qadr (Night 29)"),
        (hijri(27, 9), "Possible Laylatul Qadr (Night 27)"),
        (hijri(22, 9), None),
        (hijri(20, 9), None),
        (hijri(9, 12), "Night of Arafah"),
        (hijri(15, 8), "Laylatul Bara'ah (Night of Forgiveness)"),
        (hijri(27, 7), "Laylatul Mi'raj (Night Journey)"),
        (hijri(9, 1), "Night before Ashura"),
        (hijri(5, 3), None),
        (None, None),
    ],
)
def test_special_nights(value: HijriDate | None, expected: str | None) -> None:
    """The last night of Ramadan wins over Laylatul Qadr, whatever the month length."""
    assert get_special_night(value) == expected


def test_is_eid() -> None:
    """Eid al-Fitr is 1-3 Shawwal, Eid al-Adha 10-13 Dhul Hijjah."""
    assert is_eid(hijri(1, 10)) == "Eid al-Fitr"
    assert is_eid(hijri(3, 10)) == "Eid al-Fitr"
    assert is_eid(hijri(4, 10)) is None
    assert is_eid(hijri(10, 12)) == "Eid al-Adha"
    assert is_eid(hijri(13, 12)) == "Eid al-Adha"
    assert is_eid(hijri(9, 12)) is None
    assert is_eid(None) is None


def test_days_until_ramadan() -> None:
    """Counts to the next 1 Ramadan from the calendar, honouring the adjustment."""
    today = date(2026, 10, 20)
    current = get_hijri_date(today)
    assert current is not None
    first_ramadan = hijri_to_gregorian(1448, 9, 1)
    assert first_ramadan is not None
    assert days_until_ramadan(current, today) == (first_ramadan - today).days
    assert days_until_ramadan(current, today, adjustment_days=1) == (first_ramadan - today).days - 1
    # Inside Ramadan: None. After Ramadan: next year's.
    assert days_until_ramadan(hijri(10, 9, 1448), today) is None
    later = get_hijri_date(date(2027, 4, 1))
    assert later is not None
    assert later.month > 9
    next_first = hijri_to_gregorian(1449, 9, 1)
    assert next_first is not None
    assert days_until_ramadan(later, date(2027, 4, 1)) == (next_first - date(2027, 4, 1)).days
    assert days_until_ramadan(None, today) is None


def test_upcoming_islamic_event() -> None:
    """The next listed event after today, with its Gregorian date."""
    today = date(2026, 10, 20)  # 9 Jumada al-Awwal 1448
    current = get_hijri_date(today)
    event = upcoming_islamic_event(current, today)
    assert event is not None
    assert event.name == "Laylatul Mi'raj"
    assert event.date == hijri_to_gregorian(1448, 7, 27)
    assert event.days_until == (event.date - today).days > 0

    # On the day itself the event is "today" (0 days).
    on_the_day = upcoming_islamic_event(get_hijri_date(event.date), event.date)
    assert on_the_day is not None
    assert on_the_day.days_until == 0
    assert on_the_day.name == "Laylatul Mi'raj"

    # Year rollover: from Dhul Hijjah the next event is the Islamic New Year.
    late = hijri_to_gregorian(1448, 12, 20)
    assert late is not None
    event = upcoming_islamic_event(get_hijri_date(late), late)
    assert event is not None
    assert event.name == "Islamic New Year"
    assert event.date == hijri_to_gregorian(1449, 1, 1)
    assert upcoming_islamic_event(None, today) is None
