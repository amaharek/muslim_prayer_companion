"""Coordinator behaviour: per-minute tick, events, midnight, fallback, retry."""

from __future__ import annotations

from datetime import timedelta
import logging
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.muslim_prayer_companion.api_providers.base import (
    ProviderResponseError,
)
from custom_components.muslim_prayer_companion.api_providers.calculated import (
    CalculatedProvider,
)
from custom_components.muslim_prayer_companion.const import DOMAIN, EVENT_PRAYER_TIME
from custom_components.muslim_prayer_companion.coordinator import fallback_issue_id

from .conftest import (
    FROZEN_NOW,
    MCND_URL,
    advance,
    load_json_fixture,
    move_to,
    setup_entry,
    state_of,
)


async def test_minute_tick_updates_countdown_without_network(
    hass: HomeAssistant,
    icci_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Every minute the countdown is recomputed from cached data."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)
    assert state_of(hass, icci_entry, "next_prayer_minutes").state == "72"
    assert state_of(hass, icci_entry, "next_prayer_countdown").state == "Dhuhr in 72 minutes"

    await advance(hass, freezer, timedelta(minutes=1))

    assert state_of(hass, icci_entry, "next_prayer_minutes").state == "71"
    assert state_of(hass, icci_entry, "next_prayer_countdown").state == "Dhuhr in 71 minutes"
    assert aioclient_mock.call_count == 0


async def test_next_prayer_flips_at_prayer_time_and_fires_event(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """At Dhuhr the next prayer becomes Asr, the period shows Dhuhr, one event fires."""
    freezer.move_to("2026-10-20 12:11:30+00:00")
    await setup_entry(hass, icci_entry)
    events = async_capture_events(hass, EVENT_PRAYER_TIME)
    assert state_of(hass, icci_entry, "next_prayer").attributes["prayer"] == "Dhuhr"
    assert state_of(hass, icci_entry, "iqamah_Dhuhr").state == "2026-10-20T12:27:00+00:00"

    await move_to(hass, freezer, "2026-10-20 12:12:00+00:00")

    assert state_of(hass, icci_entry, "next_prayer").attributes["prayer"] == "Asr"
    assert state_of(hass, icci_entry, "current_prayer_period").state == "Dhuhr"
    assert state_of(hass, icci_entry, "Dhuhr").state == "2026-10-21T12:11:00+00:00"
    # The iqamah of the prayer that just started is still ahead.
    assert state_of(hass, icci_entry, "iqamah_Dhuhr").state == "2026-10-20T12:27:00+00:00"
    prayer_events = [e.data for e in events if e.data["type"] == "prayer"]
    assert prayer_events == [
        {
            "type": "prayer",
            "entry_id": icci_entry.entry_id,
            "location_name": "ICCI",
            "time": "2026-10-20T12:12:00+00:00",
            "prayer": "Dhuhr",
        }
    ]

    # 15 minutes later the (offset) iqamah event fires exactly once.
    await move_to(hass, freezer, "2026-10-20 12:27:00+00:00")
    iqamah_events = [e.data for e in events if e.data["type"] == "iqamah"]
    assert [e["prayer"] for e in iqamah_events] == ["Dhuhr"]
    assert state_of(hass, icci_entry, "iqamah_Dhuhr").state == "2026-10-21T12:26:00+00:00"

    await move_to(hass, freezer, "2026-10-20 12:28:00+00:00")
    assert len([e for e in events if e.data["type"] == "iqamah"]) == 1


async def test_midnight_refresh_loads_the_next_day(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """After local midnight the times are refetched for the new day."""
    freezer.move_to("2026-10-20 22:00:00+00:00")  # 23:00 Irish time
    await setup_entry(hass, icci_entry)
    assert state_of(hass, icci_entry, "Dhuhr").state == "2026-10-21T12:11:00+00:00"
    assert state_of(hass, icci_entry, "current_prayer_period").state == "After Isha"

    await move_to(hass, freezer, "2026-10-20 23:00:02+00:00")  # 00:00:02 Irish time, 21 Oct

    coordinator = icci_entry.runtime_data.coordinator
    assert coordinator.raw_result is not None
    assert coordinator.raw_result.today.dhuhr.isoformat() == "2026-10-21T12:11:00+00:00"
    assert state_of(hass, icci_entry, "current_prayer_period").state == "Before Fajr"
    assert state_of(hass, icci_entry, "hijri_day").state == "10"


async def test_fallback_to_calculated_with_repairs_issue(
    hass: HomeAssistant,
    mcnd_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A dead mosque API falls back to calculated times, flagged by attribute and Repairs."""
    aioclient_mock.get(MCND_URL, text="<!DOCTYPE html><html>new website</html>")
    freezer.move_to(FROZEN_NOW)
    with caplog.at_level(logging.WARNING):
        await setup_entry(hass, mcnd_entry)

    assert mcnd_entry.state is ConfigEntryState.LOADED
    maghrib = state_of(hass, mcnd_entry, "Maghrib")
    assert maghrib.attributes["source"] == "calculated-fallback:isna"
    assert maghrib.state.startswith("2026-10-20T17:")
    issue_id = fallback_issue_id(mcnd_entry.entry_id)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders["mosque"] == "Muslim Community North Dublin"
    assert "did not return JSON" in issue.translation_placeholders["error"]
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "unavailable" in r.getMessage()
    ]
    assert len(warnings) == 1

    # Still failing an hour later: a second attempt, no second warning, issue still open.
    calls_before = aioclient_mock.call_count
    await advance(hass, freezer, timedelta(hours=1, seconds=5))
    assert aioclient_mock.call_count == calls_before + 1
    assert len([r for r in caplog.records if "unavailable" in r.getMessage()]) == 1
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    assert state_of(hass, mcnd_entry, "Maghrib").attributes["source"] == "calculated-fallback:isna"

    # Recovery: the issue closes and the mosque times are back.
    aioclient_mock.clear_requests()
    aioclient_mock.get(MCND_URL, json=load_json_fixture("dpt_mcnd.json"))
    with caplog.at_level(logging.INFO):
        await advance(hass, freezer, timedelta(hours=1, seconds=5))
    assert aioclient_mock.call_count == 1
    assert state_of(hass, mcnd_entry, "Maghrib").attributes["source"] == "mcnd-api"
    assert state_of(hass, mcnd_entry, "Maghrib").state == "2026-10-20T17:23:00+00:00"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert "available again" in caplog.text


async def test_both_sources_failing_sets_up_later(
    hass: HomeAssistant,
    mcnd_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """If the fallback also fails the entry retries instead of loading with no data."""
    aioclient_mock.get(MCND_URL, status=500)
    freezer.move_to(FROZEN_NOW)
    mcnd_entry.add_to_hass(hass)
    with patch.object(
        CalculatedProvider, "async_fetch", side_effect=ProviderResponseError("no maths")
    ):
        await hass.config_entries.async_setup(mcnd_entry.entry_id)
        await hass.async_block_till_done()
    assert mcnd_entry.state is ConfigEntryState.SETUP_RETRY


async def test_todays_result_is_kept_when_refresh_fails(
    hass: HomeAssistant,
    calculated_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A calculated entry that fails later keeps today's times."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, calculated_entry)
    before = state_of(hass, calculated_entry, "Maghrib").state

    with (
        patch.object(CalculatedProvider, "async_fetch", side_effect=ProviderResponseError("boom")),
        caplog.at_level(logging.WARNING),
    ):
        await advance(hass, freezer, timedelta(hours=1, seconds=5))

    assert state_of(hass, calculated_entry, "Maghrib").state == before
    assert "keeping today's times" in caplog.text
    assert calculated_entry.runtime_data.coordinator.last_update_success is True


async def test_unexpected_exception_also_falls_back(
    hass: HomeAssistant,
    mcnd_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Even a non-provider exception from the source triggers the fallback."""
    aioclient_mock.get(MCND_URL, exc=RuntimeError("socket blocked"))
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, mcnd_entry)
    assert mcnd_entry.state is ConfigEntryState.LOADED
    assert state_of(hass, mcnd_entry, "Maghrib").attributes["source"] == "calculated-fallback:isna"
    issue = issue_registry.async_get_issue(DOMAIN, fallback_issue_id(mcnd_entry.entry_id))
    assert issue is not None
    assert "RuntimeError" in issue.translation_placeholders["error"]


async def test_mai_entry_uses_homepage(
    hass: HomeAssistant,
    mai_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_mosque_sites: AiohttpClientMocker,
) -> None:
    """The Tallaght mosque is read from its homepage; tomorrow is approximated."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, mai_entry)

    maghrib = state_of(hass, mai_entry, "Maghrib")
    assert maghrib.state == "2026-10-20T17:22:00+00:00"
    assert maghrib.attributes["source"] == "mai-website"
    # Fajr has passed and there is no tomorrow row: today's time plus one day.
    assert state_of(hass, mai_entry, "Fajr").state == "2026-10-21T05:15:00+00:00"
    assert state_of(hass, mai_entry, "Midnight").state.startswith("2026-10-21T00:")
    assert mock_mosque_sites.call_count == 1


async def test_hicc_entry_iqamah_jumuah_and_friday_device(
    hass: HomeAssistant,
    hicc_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_mosque_sites: AiohttpClientMocker,
) -> None:
    """A dpt mosque gives published iqamah, Jumu'ah and its seeded Friday sensors."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, hicc_entry)

    assert state_of(hass, hicc_entry, "Maghrib").attributes["source"] == "hicc-api"
    iqamah = state_of(hass, hicc_entry, "iqamah_Dhuhr")
    assert iqamah.state == "2026-10-20T12:32:00+00:00"  # zuhr_jamah 13:32 Irish time
    assert iqamah.attributes["source"] == "mosque"
    # Fajr jamah has passed: tomorrow's published jamah (06:37).
    assert state_of(hass, hicc_entry, "iqamah_Fajr").state == "2026-10-21T05:37:00+00:00"
    assert state_of(hass, hicc_entry, "juma_time").state == "2026-10-23T12:30:00+00:00"

    registry = er.async_get(hass)
    first = registry.async_get_entity_id(
        "sensor", DOMAIN, f"friday_hicc_jumuah_1_{hicc_entry.entry_id}"
    )
    second = registry.async_get_entity_id(
        "sensor", DOMAIN, f"friday_hicc_jumuah_2_{hicc_entry.entry_id}"
    )
    assert first is not None
    assert second is not None
    state = hass.states.get(first)
    assert state is not None
    assert state.state == "2026-10-23T12:30:00+00:00"
    assert state.attributes["label"] == "Men Only"
    assert state.attributes["times_from"] == "api"
    assert state.attributes["mosque_name"] == "Hansfield Islamic Cultural Centre"
    assert hass.states.get(second).state == "2026-10-23T13:30:00+00:00"
    # One HTTP call served prayer times, iqamah and Friday prayers.
    assert mock_mosque_sites.call_count == 1
