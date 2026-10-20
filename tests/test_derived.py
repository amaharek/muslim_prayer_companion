"""Tests for the pure derived-data builder the coordinator runs every minute."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.muslim_prayer_companion.api_providers.base import (
    IqamahTimesData,
    JumuahTime,
    PrayerTimesData,
    ProviderResult,
)
from custom_components.muslim_prayer_companion.const import (
    CONF_CALC_METHOD,
    CONF_COUNTDOWN_FORMAT,
    CONF_HIJRI_CHANGE_AT_MAGHRIB,
    CONF_IQAMAH_API_URL,
    CONF_IQAMAH_METHOD,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_PRAYER_WINDOW_MINUTES,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    IQAMAH_METHOD_API,
    IQAMAH_METHOD_DISABLED,
    IQAMAH_METHOD_MOSQUE,
    SOURCE_CALCULATED,
)
from custom_components.muslim_prayer_companion.helpers.derived import (
    DerivedInputs,
    compute_derived,
    current_prayer_period,
    format_countdown,
    next_occurrences,
    next_prayer,
)
from custom_components.muslim_prayer_companion.helpers.friday import FridayPrayerTimes
from custom_components.muslim_prayer_companion.helpers.settings import Settings

DUBLIN = ZoneInfo("Europe/Dublin")
TODAY = date(2026, 10, 20)  # Tuesday
DATA = {
    CONF_SOURCE_TYPE: SOURCE_CALCULATED,
    CONF_CALC_METHOD: "isna",
    CONF_LATITUDE: 53.3498,
    CONF_LONGITUDE: -6.2603,
    CONF_LOCATION_NAME: "Dublin",
    CONF_TIMEZONE: "Europe/Dublin",
}


def utc(day: date, hour: int, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def day_times(day: date, shift: int = 0) -> PrayerTimesData:
    """ICCI's 20 Oct row (Irish summer time) expressed in UTC, shifted by ``shift`` minutes."""
    base = [(5, 16), (6, 56), (12, 12), (14, 48), (17, 23), (18, 58)]
    times = [utc(day, h, m) + timedelta(minutes=shift) for h, m in base]
    return PrayerTimesData(
        fajr=times[0],
        sunrise=times[1],
        dhuhr=times[2],
        asr=times[3],
        maghrib=times[4],
        isha=times[5],
        source="test",
    )


def make_result(
    *, with_tomorrow: bool = True, jumuah: list[JumuahTime] | None = None
) -> ProviderResult:
    return ProviderResult(
        today=day_times(TODAY),
        tomorrow=day_times(TODAY + timedelta(days=1), shift=1) if with_tomorrow else None,
        jumuah=jumuah or [],
        source="test",
    )


def make_inputs(
    now: datetime, result: ProviderResult | None = None, **options: object
) -> DerivedInputs:
    return DerivedInputs(
        now=now,
        result=result or make_result(),
        tz=DUBLIN,
        settings=Settings.from_mappings(DATA, options),
        qibla=115.5,
        provider_name="Test",
    )


def test_next_occurrences_roll_passed_times_to_tomorrow() -> None:
    """Passed times use tomorrow's real row; future ones stay; Midnight is computed."""
    result = make_result()
    now = utc(TODAY, 11, 0)
    occurrences = next_occurrences(result, now)
    assert occurrences["Fajr"] == result.tomorrow.fajr  # type: ignore[union-attr]
    assert occurrences["Sunrise"] == result.tomorrow.sunrise  # type: ignore[union-attr]
    assert occurrences["Dhuhr"] == result.today.dhuhr
    assert occurrences["Maghrib"] == result.today.maghrib
    assert occurrences["Sunset"] == result.today.maghrib
    # Midnight: midpoint of 17:23 and tomorrow's sunrise 06:57 = 00:10.
    assert occurrences["Midnight"] == utc(TODAY + timedelta(days=1), 0, 10)


def test_next_occurrences_without_tomorrow_adds_a_day() -> None:
    """Without a tomorrow row the passed time is repeated a day later."""
    result = make_result(with_tomorrow=False)
    occurrences = next_occurrences(result, utc(TODAY, 11, 0))
    assert occurrences["Fajr"] == result.today.fajr + timedelta(days=1)
    assert occurrences["Midnight"] == utc(TODAY + timedelta(days=1), 0, 9)


def test_next_prayer_and_countdown_formats() -> None:
    """Next prayer at 11:00 UTC is Dhuhr at 12:12, 72 minutes away."""
    result = make_result()
    now = utc(TODAY, 11, 0)
    assert next_prayer(next_occurrences(result, now), now) == ("Dhuhr", result.today.dhuhr)
    assert format_countdown("Dhuhr", 72, "sentence") == "Dhuhr in 72 minutes"
    assert format_countdown("Dhuhr", 1, "sentence") == "Dhuhr in 1 minute"
    assert format_countdown("Dhuhr", 72, "clock") == "01:12"
    assert format_countdown("Dhuhr", 72, "short") == "72"
    assert format_countdown("Dhuhr", -3, "short") == "0"


@pytest.mark.parametrize(
    ("hour", "minute", "window", "expected"),
    [
        (4, 0, 30, "Before Fajr"),
        (5, 20, 30, "Fajr"),
        (5, 20, 0, "Between Fajr and Sunrise"),
        (6, 0, 30, "Between Fajr and Sunrise"),
        (7, 0, 30, "Between Sunrise and Dhuhr"),
        (12, 30, 30, "Dhuhr"),
        (13, 0, 30, "Between Dhuhr and Asr"),
        (17, 23, 30, "Maghrib"),
        (19, 10, 30, "Isha"),
        (19, 30, 30, "After Isha"),
        (23, 0, 30, "After Isha"),
    ],
)
def test_current_prayer_period(hour: int, minute: int, window: int, expected: str) -> None:
    """The period follows today's raw row, with an optional 'prayer in progress' window."""
    assert current_prayer_period(make_result(), utc(TODAY, hour, minute), window) == expected


def test_compute_derived_basics() -> None:
    """The data dict has the expected keys and values at noon on a Tuesday."""
    now = utc(TODAY, 11, 0)
    data = compute_derived(make_inputs(now))

    assert data["next_prayer_name"] == "Dhuhr"
    assert data["next_prayer_minutes"] == 72
    assert data["next_prayer_countdown"] == "Dhuhr in 72 minutes"
    assert data["current_prayer_period"] == "Between Sunrise and Dhuhr"
    assert data["is_friday"] is False
    assert data["is_ramadan"] is False
    assert data["hijri_date"] == "09-05-1448"
    assert data["special_night"] is None
    assert data["ramadan_day"] is None
    assert data["days_until_ramadan"] > 0
    assert data["upcoming_islamic_event"] == "Laylatul Mi'raj"
    assert data["imsak"] == data["Fajr"] - timedelta(minutes=10)
    assert data["iftar"] is None
    assert data["source"] == "test"
    assert data["provider"] == "Test"
    assert data["fallback_active"] is False
    assert data["qibla_direction"] == 115.5
    assert data["location_name"] == "Dublin"
    # Default iqamah: offsets after the next occurrence of each prayer.
    assert data["iqamah_Fajr"] == data["Fajr"] + timedelta(minutes=20)
    assert data["iqamah_Dhuhr"] == data["Dhuhr"] + timedelta(minutes=15)
    assert data["iqamah_source"] == "offset"
    # No Jumu'ah information: next Friday's Dhuhr (13:12 Irish time on 23 Oct).
    assert data["juma_time"] == utc(date(2026, 10, 23), 12, 12)
    assert data["friday"] == {}


def test_countdown_format_and_window_options() -> None:
    """Display options change the countdown and the period."""
    now = utc(TODAY, 12, 20)
    data = compute_derived(
        make_inputs(now, **{CONF_COUNTDOWN_FORMAT: "clock", CONF_PRAYER_WINDOW_MINUTES: 0})
    )
    assert data["next_prayer_name"] == "Asr"
    assert data["next_prayer_countdown"] == "02:28"
    assert data["current_prayer_period"] == "Between Dhuhr and Asr"


def test_iqamah_disabled() -> None:
    """Disabled iqamah adds no iqamah keys."""
    data = compute_derived(
        make_inputs(utc(TODAY, 11, 0), **{CONF_IQAMAH_METHOD: IQAMAH_METHOD_DISABLED})
    )
    assert not [key for key in data if key.startswith("iqamah_") and key != "iqamah_source"]
    assert data["iqamah_source"] is None


def test_iqamah_from_mosque_with_offset_fallback() -> None:
    """Published jamah times win; missing ones fall back to offsets; passed ones roll over."""
    result = make_result()
    result.iqamah = IqamahTimesData(
        fajr=utc(TODAY, 5, 36),
        dhuhr=utc(TODAY, 12, 32),
        maghrib=utc(TODAY, 17, 31),
    )
    result.iqamah_tomorrow = IqamahTimesData(fajr=utc(TODAY + timedelta(days=1), 5, 37))
    data = compute_derived(
        make_inputs(utc(TODAY, 11, 0), result, **{CONF_IQAMAH_METHOD: IQAMAH_METHOD_MOSQUE})
    )
    assert data["iqamah_source"] == "mosque"
    assert data["iqamah_Dhuhr"] == utc(TODAY, 12, 32)
    assert data["iqamah_Maghrib"] == utc(TODAY, 17, 31)
    assert data["iqamah_Fajr"] == utc(TODAY + timedelta(days=1), 5, 37)  # today's passed
    assert data["iqamah_Asr"] == data["Asr"] + timedelta(minutes=15)  # not published


def test_iqamah_from_api() -> None:
    """A custom API result is used when the method is 'api'."""
    inputs = make_inputs(
        utc(TODAY, 11, 0),
        **{CONF_IQAMAH_METHOD: IQAMAH_METHOD_API, CONF_IQAMAH_API_URL: "https://example.ie/iqamah"},
    )
    inputs.iqamah_api = IqamahTimesData(dhuhr=utc(TODAY, 12, 40))
    data = compute_derived(inputs)
    assert data["iqamah_source"] == "api"
    assert data["iqamah_Dhuhr"] == utc(TODAY, 12, 40)


def test_juma_time_prefers_published_then_friday_list() -> None:
    """Published Jumu'ah beats the Friday list, which beats Friday's Dhuhr."""
    now = utc(TODAY, 11, 0)
    published = compute_derived(make_inputs(now, make_result(jumuah=[JumuahTime(time(13, 30))])))
    assert published["juma_time"] == utc(date(2026, 10, 23), 12, 30)

    inputs = make_inputs(now)
    inputs.friday = [
        FridayPrayerTimes(
            slug="icci",
            name="ICCI",
            source="manual",
            tz=DUBLIN,
            times=[JumuahTime(time(13, 15), "First"), JumuahTime(time(14, 15), None)],
        )
    ]
    data = compute_derived(inputs)
    assert data["juma_time"] == utc(date(2026, 10, 23), 12, 15)
    assert data["friday"] == {
        "icci": {
            "name": "ICCI",
            "source": "manual",
            "jumuah_1": utc(date(2026, 10, 23), 12, 15),
            "jumuah_2": utc(date(2026, 10, 23), 13, 15),
            "labels": ["First", None],
            "times_from": "manual",
        }
    }


def test_hijri_changes_at_maghrib_when_enabled() -> None:
    """After Maghrib the Hijri day advances only with the option on."""
    now = utc(TODAY, 18, 0)
    assert compute_derived(make_inputs(now))["hijri_day"] == "9"
    assert (
        compute_derived(make_inputs(now, **{CONF_HIJRI_CHANGE_AT_MAGHRIB: True}))["hijri_day"]
        == "10"
    )


def test_ramadan_values() -> None:
    """During Ramadan the day number and iftar are set."""
    ramadan_day = date(2026, 3, 1)  # 12 Ramadan 1447
    result = ProviderResult(
        today=day_times(ramadan_day),
        tomorrow=day_times(ramadan_day + timedelta(days=1)),
        source="t",
    )
    data = compute_derived(make_inputs(utc(ramadan_day, 11, 0), result))
    assert data["is_ramadan"] is True
    assert data["ramadan_day"] == 12
    assert data["iftar"] == data["Maghrib"]
    assert data["days_until_ramadan"] is None
    assert data["upcoming_islamic_event"] == "Laylatul Qadr (27th night)"
