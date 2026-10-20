"""Tests for the get_prayer_times action."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.muslim_prayer_companion.const import DOMAIN, SERVICE_GET_PRAYER_TIMES

from .conftest import FROZEN_NOW, setup_entry


async def test_get_prayer_times_for_a_range(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """ICCI can answer for any date; the response has one item per day."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRAYER_TIMES,
        {"config_entry_id": icci_entry.entry_id, "date": "2026-10-20", "days": 3},
        blocking=True,
        return_response=True,
    )
    assert response["location_name"] == "ICCI"
    assert response["provider"] == "Islamic Cultural Centre of Ireland"
    days = response["days"]
    assert [day["date"] for day in days] == ["2026-10-20", "2026-10-21", "2026-10-22"]
    assert days[0]["Maghrib"] == "2026-10-20T17:23:00+00:00"
    assert days[0]["Midnight"] == "2026-10-21T00:10:00+00:00"
    assert days[0]["source"] == "icci-timetable"
    assert days[2]["Fajr"].startswith("2026-10-22T")


async def test_defaults_to_today_and_first_entry(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Without arguments: today, first loaded entry."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)
    response = await hass.services.async_call(
        DOMAIN, SERVICE_GET_PRAYER_TIMES, {}, blocking=True, return_response=True
    )
    assert [day["date"] for day in response["days"]] == ["2026-10-20"]


async def test_mosque_api_only_knows_today_and_tomorrow(
    hass: HomeAssistant,
    mcnd_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_mosque_sites: AiohttpClientMocker,
) -> None:
    """A dpt mosque serves today and tomorrow from the cached payload and refuses later dates."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, mcnd_entry)
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRAYER_TIMES,
        {"date": "2026-10-20", "days": 2},
        blocking=True,
        return_response=True,
    )
    assert len(response["days"]) == 2
    assert mock_mosque_sites.call_count == 1

    with pytest.raises(HomeAssistantError, match="only publishes today's and tomorrow's"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRAYER_TIMES,
            {"date": "2026-10-20", "days": 3},
            blocking=True,
            return_response=True,
        )


async def test_unknown_entry_and_no_entries(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Bad entry ids and a setup without entries are reported as validation errors."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRAYER_TIMES,
            {"config_entry_id": "nope"},
            blocking=True,
            return_response=True,
        )
    await hass.config_entries.async_remove(icci_entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_GET_PRAYER_TIMES, {}, blocking=True, return_response=True
        )
