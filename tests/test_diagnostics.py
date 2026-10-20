"""Diagnostics download."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import setup_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    icci_entry: MockConfigEntry,
) -> None:
    """
    Diagnostics include settings, data and bundled-file hashes, with coordinates redacted.

    Real time is used: the access token behind ``hass_client`` is issued now and
    would be "from the future" if the clock were moved backwards.
    """
    await setup_entry(hass, icci_entry)
    coordinator = icci_entry.runtime_data.coordinator

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, icci_entry)

    assert diagnostics["entry"]["data"]["latitude"] == "**REDACTED**"
    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
    assert diagnostics["settings"]["latitude"] == "**REDACTED**"
    assert diagnostics["settings"]["calc_method"] == "ie-icci"
    assert diagnostics["coordinator"]["provider"] == "Islamic Cultural Centre of Ireland"
    assert diagnostics["coordinator"]["source"] == "icci-timetable"
    assert diagnostics["coordinator"]["fallback_active"] is False
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["data"]["Maghrib"] == coordinator.data["Maghrib"].isoformat()
    assert diagnostics["coordinator"]["raw_result"]["today"]["fajr"] == (
        coordinator.raw_result.today.fajr.isoformat()
    )
    assert "raw" not in diagnostics["coordinator"]["raw_result"]
    assert diagnostics["bundled_data"]["icci_timetable_sha256"]
    assert diagnostics["bundled_data"]["mosque_registry_sha256"]
    assert diagnostics["time_zone"] == "Europe/Dublin"
