"""Set up, unload and reload of config entries."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.muslim_prayer_companion.const import DOMAIN

from .conftest import FROZEN_NOW, setup_entry, state_of


async def test_setup_calculated_entry(
    hass: HomeAssistant,
    calculated_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A calculated entry sets up offline and exposes the prayer times."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, calculated_entry)

    assert calculated_entry.state is ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 0

    maghrib = state_of(hass, calculated_entry, "Maghrib")
    # ISNA for Dublin on 20 Oct 2026: Maghrib 17:18 UTC (18:18 Irish time).
    assert maghrib.state == "2026-10-20T17:18:00+00:00"
    assert maghrib.attributes["source"] == "calculated:isna"

    next_prayer = state_of(hass, calculated_entry, "next_prayer")
    assert next_prayer.attributes["prayer"] == "Dhuhr"
    assert next_prayer.state == "2026-10-20T12:10:00+00:00"


async def test_setup_icci_entry_is_offline(
    hass: HomeAssistant,
    icci_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The ICCI entry reads the bundled timetable and makes no network request."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)

    assert icci_entry.state is ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 0

    # Table: 20 Oct = 06:16 07:56 13:12 15:48 18:23 19:58 Irish summer time.
    # At noon Fajr has passed, so the sensor shows tomorrow's (21 Oct: 06:17).
    assert state_of(hass, icci_entry, "Fajr").state == "2026-10-21T05:17:00+00:00"
    assert state_of(hass, icci_entry, "Dhuhr").state == "2026-10-20T12:12:00+00:00"
    assert state_of(hass, icci_entry, "Maghrib").state == "2026-10-20T17:23:00+00:00"
    assert state_of(hass, icci_entry, "Isha").state == "2026-10-20T18:58:00+00:00"
    # Midnight = midpoint of Maghrib 18:23 and next sunrise 07:58 = 01:10 Irish time.
    assert state_of(hass, icci_entry, "Midnight").state == "2026-10-21T00:10:00+00:00"
    assert state_of(hass, icci_entry, "Maghrib").attributes["source"] == "icci-timetable"


async def test_unload_entry(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Unloading removes the entry's state and leaves no timers behind."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)

    assert await hass.config_entries.async_unload(icci_entry.entry_id)
    await hass.async_block_till_done()

    assert icci_entry.state is ConfigEntryState.NOT_LOADED
    # Registry-backed entities stay in the state machine as unavailable.
    states = hass.states.async_all("sensor")
    assert states
    assert all(state.state == "unavailable" for state in states)


async def test_service_is_registered(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Setting up an entry registers the get_prayer_times action."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)
    assert hass.services.has_service(DOMAIN, "get_prayer_times")
