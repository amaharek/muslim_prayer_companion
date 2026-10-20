"""
Tests for the bundled ICCI timetable used by the 'ie-icci' mosque.

They cover the raw data, the fixed-clock DST rule, the Midnight calculation,
the provider wrapper and the fallback when the file is missing or corrupt.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import hashlib
import json
import logging
from zoneinfo import ZoneInfo

import pytest

from custom_components.muslim_prayer_companion.api_providers import (
    icci_timetable as icci,
)
from custom_components.muslim_prayer_companion.api_providers.base import (
    ProviderConfig,
    ProviderResponseError,
)
from custom_components.muslim_prayer_companion.api_providers.ireland import (
    IrelandProvider,
)

DUBLIN = ZoneInfo("Europe/Dublin")
TIMETABLE_SHA256 = "7309f36e1d557b84e6ba3a0697ab4f340fd23c4b8cc1843ab32c9b7feea87af6"
ICCI_CONFIG = ProviderConfig(
    latitude=53.2663,
    longitude=-6.2135,
    calculation_method="ie-icci",
    timezone="Europe/Dublin",
)


def local(value: datetime) -> str:
    """Format a UTC datetime as Irish wall-clock HH:MM."""
    return value.astimezone(DUBLIN).strftime("%H:%M")


def six_times(data: icci.PrayerTimesData) -> list[str]:
    return [
        local(t) for t in (data.fajr, data.sunrise, data.dhuhr, data.asr, data.maghrib, data.isha)
    ]


@pytest.mark.parametrize(
    ("month", "day", "expected"),
    [
        (10, 20, [[6, 16], [7, 56], [13, 12], [15, 48], [18, 23], [19, 58]]),
        (6, 21, [[2, 46], [4, 53], [13, 29], [17, 55], [22, 0], [23, 56]]),
        (2, 29, [[5, 35], [7, 14], [12, 40], [15, 24], [18, 2], [19, 35]]),
        (1, 1, [[6, 43], [8, 37], [12, 30], [14, 3], [16, 19], [18, 7]]),
        (12, 31, [[6, 43], [8, 37], [12, 30], [14, 1], [16, 18], [18, 6]]),
    ],
)
def test_raw_timetable_values(month: int, day: int, expected: list[list[int]]) -> None:
    """The bundled timetable holds ICCI's published times."""
    timetable = icci.load_icci_timetable()
    assert timetable is not None
    assert timetable[str(month)][str(day)] == expected


def test_bundled_timetable_matches_snapshot() -> None:
    """The data file is unchanged from the verified Wayback Machine snapshot."""
    data = json.loads(icci.ICCI_TIMETABLE_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(data["timetable"], sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode()).hexdigest() == TIMETABLE_SHA256
    assert sum(len(days) for days in data["timetable"].values()) == 366
    assert set(data["_source"]) == {"url", "snapshot_url", "snapshot_date", "updated", "note"}
    assert data["_source"]["updated"] == 1528119190
    assert data["_source"]["snapshot_url"].startswith("https://web.archive.org/")


@pytest.mark.parametrize(
    ("day", "hours"),
    [
        (date(2026, 3, 31), 0),
        (date(2026, 4, 1), 1),
        (date(2026, 7, 15), 1),
        (date(2026, 10, 31), 1),
        (date(2026, 11, 1), 0),
        (date(2024, 2, 29), 0),
    ],
)
def test_table_clock_offset(day: date, hours: int) -> None:
    """The table is on UTC+1 from 1 April to 31 October and UTC+0 otherwise."""
    assert icci.icci_table_utc_offset(day) == timedelta(hours=hours)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        # Table on GMT, Ireland already on summer time (DST began 28 Mar 2027): +1 h.
        (date(2027, 3, 30), ["05:24", "07:02", "13:32", "17:00", "19:57", "21:29"]),
        # Table on summer time, Ireland back on GMT (DST ended 25 Oct 2026): -1 h.
        (date(2026, 10, 27), ["05:27", "07:09", "12:11", "14:36", "17:08", "18:44"]),
        # Table and clock agree: unchanged.
        (date(2026, 10, 20), ["06:16", "07:56", "13:12", "15:48", "18:23", "19:58"]),
    ],
)
def test_dst_correction(target: date, expected: list[str]) -> None:
    """Days between the real DST change and the table's switch are shifted by an hour."""
    timetable = icci.load_icci_timetable()
    assert timetable is not None
    result = icci.build_icci_result(timetable, target)
    assert six_times(result.today) == expected
    assert result.today.sunset == result.today.maghrib
    assert result.source == "icci-timetable"
    assert result.today.source == "icci-timetable"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        # 18:23 to 07:58, both on summer time.
        (date(2026, 10, 20), "01:10"),
        # DST ends during the night: 18:15 summer time to 07:05 GMT (table 08:05 - 1 h).
        # Counting wall-clock time instead would give 00:40.
        (date(2026, 10, 24), "01:10"),
        # 16:18 to 08:37 on 1 Jan 2027.
        (date(2026, 12, 31), "00:27"),
    ],
)
def test_midnight(target: date, expected: str) -> None:
    """Midnight is halfway between Maghrib and the next day's sunrise, in UTC."""
    timetable = icci.load_icci_timetable()
    assert timetable is not None
    result = icci.build_icci_result(timetable, target)
    assert result.today.midnight is not None
    assert local(result.today.midnight) == expected
    assert result.tomorrow is not None
    assert result.tomorrow.midnight is not None


def test_tomorrow_row_and_year_rollover() -> None:
    """Tomorrow comes from the next table row, across the year end and February."""
    timetable = icci.load_icci_timetable()
    assert timetable is not None
    new_year = icci.build_icci_result(timetable, date(2026, 12, 31))
    assert new_year.tomorrow is not None
    assert new_year.tomorrow.fajr.date() == date(2027, 1, 1)
    assert local(new_year.tomorrow.fajr) == "06:43"

    non_leap = icci.build_icci_result(timetable, date(2026, 2, 28))
    assert non_leap.tomorrow is not None
    assert non_leap.tomorrow.fajr.date() == date(2026, 3, 1)

    leap = icci.build_icci_result(timetable, date(2024, 2, 28))
    assert leap.tomorrow is not None
    assert leap.tomorrow.fajr.date() == date(2024, 2, 29)
    assert local(leap.tomorrow.fajr) == "05:35"


def test_every_day_validates() -> None:
    """Every row of a leap year and a normal year is strictly increasing in UTC."""
    timetable = icci.load_icci_timetable()
    assert timetable is not None
    for year in (2024, 2026):
        for month in range(1, 13):
            for day in range(1, calendar.monthrange(year, month)[1] + 1):
                result = icci.build_icci_result(timetable, date(year, month, day))
                result.today.validate()


@pytest.mark.parametrize(
    ("prayers", "valid"),
    [
        ([[6, 43], [8, 37], [12, 30], [14, 3], [16, 19], [18, 7]], True),
        ([[6, 43], [8, 37]], False),
        ([[6, 43], [8, 37], [12, 30], [14, 3], [16, 19], [24, 7]], False),
        ([[6, 43], [8, 37], [12, 30], [14, 3], [16, 19], [18, 60]], False),
        ([[6, 43], [8, 37], [12, 30], [14, 3], [16, 19], ["18", 7]], False),
        ("not a list", False),
    ],
)
def test_is_valid_icci_day(prayers: object, valid: bool) -> None:
    """A day is six [hour, minute] pairs of ints in range."""
    assert icci.is_valid_icci_day(prayers) is valid


@pytest.mark.parametrize(
    "content",
    [
        None,
        "{not json",
        json.dumps({"_source": {}}),
        json.dumps({"timetable": {"1": {"1": [[6, 43], [8, 37]]}}}),
    ],
    ids=["missing", "invalid-json", "no-timetable", "truncated-day"],
)
def test_missing_or_corrupt_timetable(
    tmp_path: object,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    content: str | None,
) -> None:
    """A bad file gives None, with a single warning however often it is asked."""
    path = tmp_path / "icci_timetable.json"  # type: ignore[operator]
    if content is not None:
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(icci, "ICCI_TIMETABLE_PATH", path)
    icci.load_icci_timetable.cache_clear()

    with caplog.at_level(logging.WARNING):
        assert icci.load_icci_timetable() is None
        assert icci.load_icci_timetable() is None

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "missing or corrupt" in warnings[0].getMessage()


async def test_icci_provider_reads_the_table() -> None:
    """The Ireland provider serves ICCI from the bundled table, with tomorrow and Midnight."""
    provider = IrelandProvider(ICCI_CONFIG)
    result = await provider.async_fetch(date(2026, 10, 20))
    assert local(result.today.maghrib) == "18:23"
    assert result.tomorrow is not None
    assert local(result.tomorrow.fajr) == "06:17"
    assert result.today.midnight is not None
    assert result.jumuah == []
    assert result.iqamah is None
    assert provider.supports_any_date is True
    assert provider.supports_iqamah is False
    assert provider.supports_jumuah is False


async def test_icci_provider_corrupt_file_raises(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt bundled file surfaces as a provider error (so the coordinator falls back)."""
    monkeypatch.setattr(icci, "ICCI_TIMETABLE_PATH", tmp_path / "missing.json")  # type: ignore[operator]
    icci.load_icci_timetable.cache_clear()
    provider = IrelandProvider(ICCI_CONFIG)
    with pytest.raises(ProviderResponseError, match="missing or corrupt"):
        await provider.async_fetch(date(2026, 10, 20))
