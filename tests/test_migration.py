"""Config entry migration from versions 1 (3.0.x) and 2 to version 3."""

from __future__ import annotations

import logging

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.muslim_prayer_companion import migrate_options
from custom_components.muslim_prayer_companion.const import (
    CONF_CALC_METHOD,
    CONF_ENABLED_GROUPS,
    CONF_FRIDAY_MOSQUES,
    CONF_IQAMAH_METHOD,
    CONF_IQAMAH_OFFSETS,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    CONFIG_VERSION,
    DOMAIN,
    GROUP_COUNTDOWN,
    GROUP_HIJRI,
    IQAMAH_METHOD_DISABLED,
    IQAMAH_METHOD_MOSQUE,
    IQAMAH_METHOD_OFFSET,
    SENSOR_GROUPS,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
)

from .conftest import DUBLIN_LAT, DUBLIN_LON, FROZEN_NOW


def v1_entry(
    data: dict, options: dict | None = None, title: str = "Muslim Prayer Companion"
) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, version=1, title=title, data=data, options=options or {})


async def test_v1_ireland_entry(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """A 3.0.x ICCI entry becomes a version 3 Irish entry with seeded options."""
    freezer.move_to(FROZEN_NOW)
    entry = v1_entry({CONF_CALC_METHOD: "ie-icci"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == CONFIG_VERSION
    assert entry.data[CONF_SOURCE_TYPE] == SOURCE_IRELAND
    assert entry.data[CONF_CALC_METHOD] == "ie-icci"
    # Version 1 had no coordinates: Home Assistant's are used, never overwritten later.
    assert entry.data[CONF_LATITUDE] == DUBLIN_LAT
    assert entry.data[CONF_LONGITUDE] == DUBLIN_LON
    assert entry.data[CONF_TIMEZONE] == "Europe/Dublin"
    assert entry.data[CONF_LOCATION_NAME] == "ICCI"
    assert entry.unique_id == "ireland:ie-icci"
    assert entry.options[CONF_IQAMAH_METHOD] == IQAMAH_METHOD_OFFSET
    assert entry.options[CONF_FRIDAY_MOSQUES][0]["source"] == "manual"
    assert entry.options[CONF_ENABLED_GROUPS] == list(SENSOR_GROUPS)
    assert CONF_CALC_METHOD not in entry.options


async def test_v1_calculated_entry_honours_options_method(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """3.0.x read the method from options first, so that is what is migrated."""
    freezer.move_to(FROZEN_NOW)
    entry = v1_entry({CONF_CALC_METHOD: "isna"}, {CONF_CALC_METHOD: "mwl"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data[CONF_SOURCE_TYPE] == SOURCE_CALCULATED
    assert entry.data[CONF_CALC_METHOD] == "mwl"
    assert entry.options[CONF_CALC_METHOD] == "mwl"
    assert entry.data[CONF_LOCATION_NAME] == "Home"
    assert entry.unique_id == f"calculated:{DUBLIN_LAT:.4f},{DUBLIN_LON:.4f}"


async def test_duplicate_v1_entries_do_not_collide(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, caplog: pytest.LogCaptureFixture
) -> None:
    """Two identical 3.0.x entries: the second keeps no unique id instead of colliding."""
    freezer.move_to(FROZEN_NOW)
    first = v1_entry({CONF_CALC_METHOD: "ie-icci"}, title="First")
    second = v1_entry({CONF_CALC_METHOD: "ie-icci"}, title="Second")
    first.add_to_hass(hass)
    second.add_to_hass(hass)
    with caplog.at_level(logging.WARNING):
        # Setting up the component sets up every entry of the domain.
        assert await hass.config_entries.async_setup(first.entry_id)
        await hass.async_block_till_done()
    assert second.state is ConfigEntryState.LOADED
    assert first.unique_id == "ireland:ie-icci"
    assert second.unique_id is None
    assert second.version == CONFIG_VERSION
    assert "duplicates" in caplog.text


async def test_newer_version_is_refused(hass: HomeAssistant) -> None:
    """An entry from a newer release is not migrated downwards."""
    entry = MockConfigEntry(domain=DOMAIN, version=CONFIG_VERSION + 1, data={})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


def test_migrate_options_v2_toggles_and_iqamah() -> None:
    """The never-applied enable_* toggles become groups; iqamah settings carry over."""
    data = {
        CONF_SOURCE_TYPE: SOURCE_IRELAND,
        CONF_CALC_METHOD: "ie-hicc",
        CONF_LATITUDE: 1.0,
        CONF_LONGITUDE: 2.0,
    }
    options = {
        "enable_hijri": False,
        "enable_countdown": True,
        CONF_IQAMAH_METHOD: IQAMAH_METHOD_OFFSET,
        CONF_IQAMAH_OFFSETS: {"Fajr": 25, "Dhuhr": "bad"},
        "future_key": 1,
    }
    new_data, new_options = migrate_options(data, options)
    assert new_data[CONF_CALC_METHOD] == "ie-hicc"
    assert new_data[CONF_LATITUDE] == 1.0
    assert GROUP_HIJRI not in new_options[CONF_ENABLED_GROUPS]
    assert GROUP_COUNTDOWN in new_options[CONF_ENABLED_GROUPS]
    # HICC publishes jamah times: the mosque default wins over the old 'offset'.
    assert new_options[CONF_IQAMAH_METHOD] == IQAMAH_METHOD_MOSQUE
    assert new_options[CONF_IQAMAH_OFFSETS]["Fajr"] == 25
    assert new_options[CONF_IQAMAH_OFFSETS]["Dhuhr"] == 15
    assert new_options["future_key"] == 1
    assert new_options[CONF_FRIDAY_MOSQUES][0]["source"] == "ie-hicc"
    assert "enable_hijri" not in new_options


def test_migrate_options_keeps_disabled_iqamah_and_unknown_method() -> None:
    """Disabled stays disabled; an unknown method falls back to ISNA."""
    data, options = migrate_options(
        {CONF_CALC_METHOD: "weird"}, {CONF_IQAMAH_METHOD: IQAMAH_METHOD_DISABLED}
    )
    assert data[CONF_SOURCE_TYPE] == SOURCE_CALCULATED
    assert data[CONF_CALC_METHOD] == "isna"
    assert options[CONF_CALC_METHOD] == "isna"
    assert options[CONF_IQAMAH_METHOD] == IQAMAH_METHOD_DISABLED
