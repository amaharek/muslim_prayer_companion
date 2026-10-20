"""Tests for the Hijri date helpers (hijridate, adjustment, Maghrib rollover)."""

from __future__ import annotations

from datetime import UTC, date, datetime
import logging
from zoneinfo import ZoneInfo

from hijridate import Hijri
import pytest

from custom_components.muslim_prayer_companion.helpers.hijri import (
    HijriDate,
    effective_hijri_date,
    get_hijri_date,
    hijri_to_gregorian,
)

DUBLIN = ZoneInfo("Europe/Dublin")


@pytest.mark.parametrize(
    ("gregorian", "year", "month", "day", "month_name"),
    [
        (date(2026, 10, 20), 1448, 5, 9, "Jumada al-Awwal"),
        (date(2025, 6, 26), 1447, 1, 1, "Muharram"),
        (date(2026, 6, 16), 1448, 1, 1, "Muharram"),
        (date(2026, 3, 18), 1447, 9, 29, "Ramadan"),
    ],
)
def test_known_dates(gregorian: date, year: int, month: int, day: int, month_name: str) -> None:
    """Umm al-Qura anchors."""
    hijri = get_hijri_date(gregorian)
    assert hijri == HijriDate(day, month, year, month_name, hijri.month_length)
    assert hijri.month_length in (29, 30)


def test_ramadan_1447_has_30_days() -> None:
    """month_length comes from the calendar, which the Eid-night logic relies on."""
    hijri = get_hijri_date(date(2026, 3, 18))
    assert hijri is not None
    assert hijri.month_length == Hijri(1447, 9, 1).month_length() == 30


@pytest.mark.parametrize(("adjustment", "day"), [(-2, 7), (-1, 8), (0, 9), (1, 10), (2, 11)])
def test_adjustment_shifts_the_day(adjustment: int, day: int) -> None:
    """The adjustment moves the Hijri date by whole days."""
    hijri = get_hijri_date(date(2026, 10, 20), adjustment_days=adjustment)
    assert hijri is not None
    assert hijri.day == day


def test_out_of_range_returns_none_and_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    """Dates outside the calendar give None with a single warning."""
    with caplog.at_level(logging.WARNING):
        assert get_hijri_date(date(2100, 1, 1)) is None
        assert get_hijri_date(date(2100, 1, 1)) is None
    assert len([r for r in caplog.records if "Cannot convert" in r.getMessage()]) == 1


def test_effective_hijri_date_maghrib_rollover() -> None:
    """After Maghrib the Hijri day advances only when the option is on."""
    maghrib = datetime(2026, 10, 20, 17, 23, tzinfo=UTC)
    before = datetime(2026, 10, 20, 11, 0, tzinfo=UTC)
    after = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)

    assert effective_hijri_date(before, DUBLIN, maghrib, change_at_maghrib=False).day == 9
    assert effective_hijri_date(before, DUBLIN, maghrib, change_at_maghrib=True).day == 9
    assert effective_hijri_date(after, DUBLIN, maghrib, change_at_maghrib=False).day == 9
    assert effective_hijri_date(after, DUBLIN, maghrib, change_at_maghrib=True).day == 10
    # Without a Maghrib time the option cannot apply.
    assert effective_hijri_date(after, DUBLIN, None, change_at_maghrib=True).day == 9
    # Local date, not UTC date: 23:30 UTC is already 21 Oct in Dublin (summer time).
    late = datetime(2026, 10, 20, 23, 30, tzinfo=UTC)
    assert effective_hijri_date(late, DUBLIN, maghrib).day == 10


def test_hijri_to_gregorian_with_adjustment() -> None:
    """A Hijri date falls one Gregorian day earlier per +1 of adjustment."""
    assert hijri_to_gregorian(1448, 1, 1) == date(2026, 6, 16)
    assert hijri_to_gregorian(1448, 1, 1, adjustment_days=1) == date(2026, 6, 15)
    assert hijri_to_gregorian(1448, 1, 1, adjustment_days=-1) == date(2026, 6, 17)
    assert hijri_to_gregorian(1600, 1, 1) is None


def test_to_dict_formats() -> None:
    """Sensor values keep the 2.x formats."""
    hijri = get_hijri_date(date(2026, 3, 18))
    assert hijri is not None
    assert hijri.to_dict() == {
        "hijri_date": "29-09-1447",
        "hijri_day": "29",
        "hijri_month_num": 9,
        "hijri_month_readable": "Ramadan",
        "hijri_year": "1447",
        "hijri_date_readable": "29-Ramadan-1447",
        "hijri_day_month_readable": "29-Ramadan",
    }
