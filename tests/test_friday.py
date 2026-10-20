"""Tests for the Friday prayers helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
import logging
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.muslim_prayer_companion.api_providers.base import (
    JumuahTime,
    PrayerTimesData,
    ProviderResult,
)
from custom_components.muslim_prayer_companion.const import (
    CONF_FRIDAY_JUMUAH_1,
    CONF_FRIDAY_JUMUAH_2,
    CONF_FRIDAY_LABEL_1,
    CONF_FRIDAY_NAME,
    CONF_FRIDAY_SLUG,
    CONF_FRIDAY_SOURCE,
    FRIDAY_SOURCE_MANUAL,
)
from custom_components.muslim_prayer_companion.helpers.friday import (
    FridayMosqueConfig,
    FridayPrayersFetcher,
    friday_item_from_input,
    next_friday_occurrence,
    normalise_hhmm,
    parse_hhmm,
    seed_friday_mosques,
    slug_for,
    validate_friday_item,
)

from .conftest import HICC_URL, load_json_fixture

DUBLIN = ZoneInfo("Europe/Dublin")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("13:30", time(13, 30)),
        ("9:05", time(9, 5)),
        ("13:30:00", time(13, 30)),
        (time(13, 30, 15), time(13, 30)),
        ("24:00", None),
        ("13:60", None),
        ("junk", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_hhmm(value: object, expected: time | None) -> None:
    """Clock strings are parsed leniently."""
    assert parse_hhmm(value) == expected


def test_normalise_hhmm_and_slug() -> None:
    """Canonical HH:MM strings and stable slugs."""
    assert normalise_hhmm("9:05") == "09:05"
    assert normalise_hhmm("junk") is None
    assert slug_for("Islamic Cultural Centre of Ireland") == "islamic_cultural_centre_of_ireland"
    assert slug_for("  ") == "unknown"  # Home Assistant's slugify fallback
    assert len(slug_for("a" * 100)) <= 40


def test_config_round_trip_and_unknown_source() -> None:
    """Stored dicts round-trip; an unknown source becomes manual."""
    item = {
        CONF_FRIDAY_SLUG: "icci",
        CONF_FRIDAY_NAME: "ICCI",
        CONF_FRIDAY_SOURCE: "ie-icci",
        CONF_FRIDAY_JUMUAH_1: "13:30",
        CONF_FRIDAY_JUMUAH_2: None,
        CONF_FRIDAY_LABEL_1: " Men only ",
        "label_2": None,
    }
    config = FridayMosqueConfig.from_dict(item)
    assert config.jumuah_1 == time(13, 30)
    assert config.label_1 == "Men only"
    assert config.timezone == "Europe/Dublin"
    assert config.manual_times == [JumuahTime(time(13, 30), "Men only")]
    assert config.to_dict() == {**item, CONF_FRIDAY_LABEL_1: "Men only"}

    unknown = FridayMosqueConfig.from_dict({CONF_FRIDAY_NAME: "X", CONF_FRIDAY_SOURCE: "ie-nope"})
    assert unknown.source == FRIDAY_SOURCE_MANUAL
    assert unknown.slug == "x"
    assert unknown.timezone is None


def test_seed_friday_mosques() -> None:
    """Mosques that publish Jumu'ah times are seeded as auto, others as manual."""
    assert seed_friday_mosques(None) == []
    assert seed_friday_mosques("isna") == []
    hicc = seed_friday_mosques("ie-hicc")[0]
    assert hicc[CONF_FRIDAY_SOURCE] == "ie-hicc"
    assert hicc[CONF_FRIDAY_SLUG] == "hicc"
    icci = seed_friday_mosques("ie-icci")[0]
    assert icci[CONF_FRIDAY_SOURCE] == FRIDAY_SOURCE_MANUAL
    assert icci[CONF_FRIDAY_NAME] == "Islamic Cultural Centre of Ireland"


def test_validate_friday_item() -> None:
    """Every validation rule."""
    existing = [{CONF_FRIDAY_SLUG: "icci", CONF_FRIDAY_NAME: "ICCI"}]
    ok = {CONF_FRIDAY_NAME: "MAI", CONF_FRIDAY_SOURCE: "manual", CONF_FRIDAY_JUMUAH_1: "13:30"}
    assert validate_friday_item(ok, existing) == {}

    assert validate_friday_item(
        {CONF_FRIDAY_SOURCE: "manual", CONF_FRIDAY_JUMUAH_1: "13:30"}, existing
    ) == {CONF_FRIDAY_NAME: "name_required"}
    assert (
        validate_friday_item({**ok, CONF_FRIDAY_NAME: "icci"}, existing)[CONF_FRIDAY_NAME]
        == "name_exists"
    )
    # Editing the same mosque may keep its own name.
    assert (
        validate_friday_item({**ok, CONF_FRIDAY_NAME: "ICCI"}, existing, editing_slug="icci") == {}
    )
    assert validate_friday_item({**ok, CONF_FRIDAY_JUMUAH_1: "25:00"}, existing) == {
        CONF_FRIDAY_JUMUAH_1: "invalid_time"
    }
    assert validate_friday_item({**ok, CONF_FRIDAY_JUMUAH_1: ""}, existing) == {
        CONF_FRIDAY_JUMUAH_1: "time_required"
    }
    assert (
        validate_friday_item(
            {**ok, CONF_FRIDAY_SOURCE: "ie-hicc", CONF_FRIDAY_JUMUAH_1: ""}, existing
        )
        == {}
    )
    assert validate_friday_item({**ok, CONF_FRIDAY_JUMUAH_2: "13:00"}, existing) == {
        CONF_FRIDAY_JUMUAH_2: "jumuah_order"
    }
    assert validate_friday_item({**ok, CONF_FRIDAY_LABEL_1: "x" * 41}, existing) == {
        CONF_FRIDAY_LABEL_1: "label_too_long"
    }
    assert validate_friday_item({**ok, CONF_FRIDAY_SOURCE: "ie-nope"}, existing) == {
        CONF_FRIDAY_SOURCE: "unknown_source"
    }
    many = [{CONF_FRIDAY_SLUG: f"m{i}", CONF_FRIDAY_NAME: f"M{i}"} for i in range(10)]
    assert validate_friday_item(ok, many)["base"] == "too_many_mosques"
    assert "base" not in validate_friday_item(ok, many, editing_slug="m1")


def test_friday_item_from_input() -> None:
    """Form input becomes a normalised stored dict; the slug is kept when editing."""
    item = friday_item_from_input(
        {
            CONF_FRIDAY_NAME: " MAI Tallaght ",
            CONF_FRIDAY_JUMUAH_1: "13:30",
            CONF_FRIDAY_LABEL_1: "",
        },
    )
    assert item[CONF_FRIDAY_SLUG] == "mai_tallaght"
    assert item[CONF_FRIDAY_NAME] == "MAI Tallaght"
    assert item[CONF_FRIDAY_SOURCE] == FRIDAY_SOURCE_MANUAL
    assert item[CONF_FRIDAY_JUMUAH_1] == "13:30"
    assert item[CONF_FRIDAY_LABEL_1] is None
    edited = friday_item_from_input(
        {CONF_FRIDAY_NAME: "New name", CONF_FRIDAY_JUMUAH_1: "13:30"}, slug="old"
    )
    assert edited[CONF_FRIDAY_SLUG] == "old"


@pytest.mark.parametrize(
    ("now", "clock", "expected"),
    [
        # Tuesday noon: this Friday at 13:30 Irish summer time.
        (
            datetime(2026, 10, 20, 11, 0, tzinfo=UTC),
            time(13, 30),
            datetime(2026, 10, 23, 12, 30, tzinfo=UTC),
        ),
        # Friday 13:00 Irish time: still today.
        (
            datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
            time(13, 30),
            datetime(2026, 10, 23, 12, 30, tzinfo=UTC),
        ),
        # Friday 14:00 Irish time: next week, now on GMT (DST ended 25 Oct).
        (
            datetime(2026, 10, 23, 13, 0, tzinfo=UTC),
            time(13, 30),
            datetime(2026, 10, 30, 13, 30, tzinfo=UTC),
        ),
        # Saturday: next Friday.
        (
            datetime(2026, 10, 24, 9, 0, tzinfo=UTC),
            time(13, 30),
            datetime(2026, 10, 30, 13, 30, tzinfo=UTC),
        ),
    ],
)
def test_next_friday_occurrence(now: datetime, clock: time, expected: datetime) -> None:
    """The next Friday at a wall-clock time, across the DST change."""
    assert next_friday_occurrence(now, clock, DUBLIN) == expected


def _own_result() -> ProviderResult:
    day = datetime(2026, 10, 20, tzinfo=UTC)
    today = PrayerTimesData(
        fajr=day.replace(hour=5),
        sunrise=day.replace(hour=7),
        dhuhr=day.replace(hour=12),
        asr=day.replace(hour=15),
        maghrib=day.replace(hour=17),
        isha=day.replace(hour=19),
    )
    return ProviderResult(today=today, jumuah=[JumuahTime(time(13, 0), "Own")], source="x")


async def test_fetcher_manual_and_own_mosque() -> None:
    """Manual configs use their stored times; the entry's own mosque reuses its result."""
    configs = [
        FridayMosqueConfig(slug="manual", name="Manual", jumuah_1=time(13, 30), label_1="A"),
        FridayMosqueConfig(slug="hicc", name="HICC", source="ie-hicc"),
    ]
    fetcher = FridayPrayersFetcher(None, configs, DUBLIN)
    resolved = await fetcher.async_update(date(2026, 10, 20), _own_result(), "ie-hicc")
    assert resolved[0].times == [JumuahTime(time(13, 30), "A")]
    assert resolved[0].times_from == "manual"
    assert resolved[1].times == [JumuahTime(time(13, 0), "Own")]
    assert resolved[1].times_from == "api"
    assert resolved[1].tz == DUBLIN


async def test_fetcher_fetches_other_mosque_once_per_day(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Another dpt mosque is fetched once per day and cached."""
    aioclient_mock.get(HICC_URL, json=load_json_fixture("dpt_hicc.json"))
    session = aioclient_mock.create_session(hass.loop)
    fetcher = FridayPrayersFetcher(
        session, [FridayMosqueConfig(slug="hicc", name="HICC", source="ie-hicc")], DUBLIN
    )

    resolved = await fetcher.async_update(date(2026, 10, 20), None, "ie-icci")
    assert [s.clock for s in resolved[0].times] == [time(13, 30), time(14, 30)]
    assert resolved[0].times_from == "api"
    assert aioclient_mock.call_count == 1

    await fetcher.async_update(date(2026, 10, 20), None, "ie-icci")
    assert aioclient_mock.call_count == 1  # payload cache
    await session.close()


async def test_fetcher_failure_uses_manual_fallback_and_warns_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing mosque API falls back to the stored times with a single warning."""
    aioclient_mock.get(HICC_URL, status=500)
    session = aioclient_mock.create_session(hass.loop)
    config = FridayMosqueConfig(slug="hicc", name="HICC", source="ie-hicc", jumuah_1=time(13, 45))
    fetcher = FridayPrayersFetcher(session, [config], DUBLIN)

    with caplog.at_level(logging.WARNING):
        first = await fetcher.async_update(date(2026, 10, 20), None, None)
        fetcher._providers["ie-hicc"].clear_cache()
        second = await fetcher.async_update(date(2026, 10, 20), None, None)
    assert first[0].times == [JumuahTime(time(13, 45))]
    assert first[0].times_from == "manual"
    assert second[0].times_from == "manual"
    assert (
        len([r for r in caplog.records if "Could not fetch Friday prayer times" in r.getMessage()])
        == 1
    )

    # Recovery: the API works again and an info line is logged.
    aioclient_mock.clear_requests()
    aioclient_mock.get(HICC_URL, json=load_json_fixture("dpt_hicc.json"))
    fetcher._providers["ie-hicc"].clear_cache()
    with caplog.at_level(logging.INFO):
        third = await fetcher.async_update(date(2026, 10, 20), None, None)
    assert third[0].times_from == "api"
    assert "available again" in caplog.text
    await session.close()


async def test_fetcher_registry_mosque_without_published_times() -> None:
    """A registry mosque that does not publish Jumu'ah (ICCI) uses the stored times."""
    config = FridayMosqueConfig(slug="icci", name="ICCI", source="ie-icci", jumuah_1=time(13, 30))
    resolved = await FridayPrayersFetcher(None, [config], DUBLIN).async_update(
        date(2026, 10, 20), None, None
    )
    assert resolved[0].times == [JumuahTime(time(13, 30))]
    assert resolved[0].times_from == "manual"
