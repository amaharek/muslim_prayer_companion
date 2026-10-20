"""
Test cases for the bundled ICCI timetable used by the 'ie-icci' calculation method.
These tests cover the raw timetable data, the DST correction, the Midnight
calculation and the fallback when the timetable file is missing or corrupt.
"""

import hashlib
import json
import logging
from datetime import UTC, date, datetime
from unittest.mock import patch

import homeassistant.util.dt as dt_util
import pytest
from astral import Observer
from astral.sun import sunset
from freezegun import freeze_time
from test_helpers import create_fake_config_entry, create_fake_hass

from custom_components.muslim_prayer_companion import const, coordinator

# Islamic Cultural Centre of Ireland, Clonskeagh, Dublin.
ICCI_LATITUDE = 53.2663
ICCI_LONGITUDE = -6.2135
TIMETABLE_SHA256 = "7309f36e1d557b84e6ba3a0697ab4f340fd23c4b8cc1843ab32c9b7feea87af6"


def dublin_sunset(hass, event, target_date):
    """Stand in for get_astral_event_date: the real sunset at ICCI, in UTC."""
    assert event == "sunset"
    observer = Observer(latitude=ICCI_LATITUDE, longitude=ICCI_LONGITUDE)
    return sunset(observer, target_date, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clear_timetable_cache():
    """Make every test load the timetable again."""
    coordinator.load_icci_timetable.cache_clear()
    yield
    coordinator.load_icci_timetable.cache_clear()


@pytest.fixture
def dublin_time_zone():
    """Use Irish local time for the duration of a test."""
    original = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Dublin"))
    yield
    dt_util.set_default_time_zone(original)


@pytest.fixture
def icci_coordinator(dublin_time_zone):
    """Return a coordinator for the 'ie-icci' method, located in Dublin."""
    hass = create_fake_hass()
    hass.config.latitude = ICCI_LATITUDE
    hass.config.longitude = ICCI_LONGITUDE
    # Newer Home Assistant versions report the missing config_entry argument
    # through the frame helper, which is not set up with a fake hass.
    with patch("homeassistant.helpers.frame.report_usage"):
        coord = coordinator.MuslimPrayerCompanionDataUpdateCoordinator(hass)
    coord.config_entry = create_fake_config_entry(
        options={const.CONF_CALC_METHOD: "ie-icci"}
    )
    return coord


@pytest.fixture
def offline_coordinator(icci_coordinator):
    """
    Return the 'ie-icci' coordinator with Dublin sunsets, failing on any
    network request or ISNA fallback.
    """
    with (
        patch.object(coordinator, "get_astral_event_date", side_effect=dublin_sunset),
        patch.object(
            coordinator, "get_json_response", side_effect=AssertionError("network")
        ),
        patch.object(
            coordinator, "PrayerTimesCalculator", side_effect=AssertionError("network")
        ),
        patch.object(
            icci_coordinator,
            "_get_prayer_times_standard",
            side_effect=AssertionError("ISNA fallback"),
        ),
    ):
        yield icci_coordinator


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
def test_raw_timetable_values(month, day, expected):
    """Test that the bundled timetable holds ICCI's published times."""
    timetable = coordinator.load_icci_timetable()
    assert timetable[str(month)][str(day)] == expected


def test_bundled_timetable_matches_snapshot():
    """Test that the bundled timetable is unchanged from the verified snapshot."""
    data = json.loads(coordinator.ICCI_TIMETABLE_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(data["timetable"], sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode()).hexdigest() == TIMETABLE_SHA256
    assert sum(len(days) for days in data["timetable"].values()) == 366
    assert set(data["_source"]) == {
        "url",
        "snapshot_url",
        "snapshot_date",
        "updated",
        "note",
    }
    assert data["_source"]["updated"] == 1528119190


def test_prayer_time_keys(offline_coordinator):
    """Test that 'ie-icci' returns the same keys as the other methods."""
    prayer_times = offline_coordinator._get_prayer_times_ie_icci(date(2026, 10, 20))
    assert set(prayer_times) == {
        "Fajr",
        "Sunrise",
        "Dhuhr",
        "Asr",
        "Sunset",
        "Maghrib",
        "Isha",
        "Imsak",
        "Midnight",
    }


@pytest.mark.parametrize(
    ("target_date", "expected"),
    [
        # The table holds GMT times, but DST started on 28 Mar 2027: +1 h.
        (
            date(2027, 3, 30),
            ["05:24", "07:02", "13:32", "17:00", "19:57", "21:29"],
        ),
        # The table holds summer times, but DST ended on 25 Oct 2026: -1 h.
        (
            date(2026, 10, 27),
            ["05:27", "07:09", "12:11", "14:36", "17:08", "18:44"],
        ),
        # The table and the real clock agree: unchanged.
        (
            date(2026, 10, 20),
            ["06:16", "07:56", "13:12", "15:48", "18:23", "19:58"],
        ),
    ],
)
def test_dst_correction(offline_coordinator, target_date, expected):
    """Test that days on the wrong clock are shifted by one hour."""
    prayer_times = offline_coordinator._get_prayer_times_ie_icci(target_date)
    names = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
    assert [prayer_times[name] for name in names] == expected
    assert prayer_times["Sunset"] == prayer_times["Maghrib"]


@pytest.mark.parametrize(
    ("table_maghrib", "local_sunset", "expected"),
    [
        ([18, 23], datetime(2026, 10, 20, 18, 17), 0),
        ([18, 57], datetime(2027, 3, 30, 19, 55), 1),
        ([18, 8], datetime(2026, 10, 27, 17, 2), -1),
        ([18, 30], datetime(2026, 10, 20, 18, 0), 0),
        ([18, 31], datetime(2026, 10, 20, 18, 0), -1),
        ([17, 30], datetime(2026, 10, 20, 18, 0), 0),
        ([17, 29], datetime(2026, 10, 20, 18, 0), 1),
    ],
)
def test_get_dst_hour_offset(table_maghrib, local_sunset, expected):
    """Test the hour fix: only a gap of more than 30 minutes shifts the day."""
    local_sunset = local_sunset.replace(tzinfo=dt_util.get_time_zone("Europe/Dublin"))
    assert (
        coordinator.get_dst_hour_offset(
            table_maghrib, local_sunset.date(), local_sunset
        )
        == expected
    )


def test_dst_correction_without_sunset(icci_coordinator):
    """Test the ISNA comparison used when there is no sunset at the location."""
    with (
        patch.object(coordinator, "get_astral_event_date", return_value=None),
        patch.object(
            icci_coordinator,
            "_get_prayer_times_standard",
            return_value={"Maghrib": "19:56"},
        ),
    ):
        prayer_times = icci_coordinator._get_prayer_times_ie_icci(date(2027, 3, 30))
    assert prayer_times["Maghrib"] == "19:57"


@pytest.mark.parametrize(
    ("target_date", "expected"),
    [
        # 18:23 to 07:58, both in summer time.
        (date(2026, 10, 20), "01:10"),
        # DST ends during the night: 18:15 summer time to 07:05 GMT (table 08:05 - 1 h).
        # Counting wall-clock time instead would give 00:40.
        (date(2026, 10, 24), "01:10"),
        # 16:18 to 08:37 on 1 Jan 2027.
        (date(2026, 12, 31), "00:27"),
    ],
)
def test_midnight(offline_coordinator, target_date, expected):
    """Test Midnight: halfway between Maghrib and the next day's sunrise."""
    prayer_times = offline_coordinator._get_prayer_times_ie_icci(target_date)
    assert prayer_times["Midnight"] == expected


@freeze_time("2026-10-20 12:00:00")
def test_get_new_prayer_times_uses_timetable(offline_coordinator):
    """Test that the 'ie-icci' method reads the bundled timetable for today."""
    prayer_times = offline_coordinator.get_new_prayer_times()
    assert prayer_times["Maghrib"] == "18:23"
    assert prayer_times["Midnight"] == "01:10"


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
def test_missing_or_corrupt_timetable(icci_coordinator, tmp_path, caplog, content):
    """Test the ISNA fallback, with a single warning across refreshes."""
    path = tmp_path / "icci_timetable.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    isna_prayers = {"Fajr": "06:00", "Maghrib": "18:00"}
    with (
        patch.object(coordinator, "ICCI_TIMETABLE_PATH", path),
        patch.object(
            icci_coordinator, "_get_prayer_times_standard", return_value=isna_prayers
        ) as standard,
        caplog.at_level(logging.WARNING),
    ):
        first = icci_coordinator._get_prayer_times_ie_icci(date(2026, 10, 20))
        second = icci_coordinator._get_prayer_times_ie_icci(date(2026, 10, 21))

    assert first == second == isna_prayers
    assert standard.call_count == 2
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "missing or corrupt" in warnings[0].getMessage()
