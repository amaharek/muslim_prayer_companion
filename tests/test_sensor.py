"""Sensor platform: descriptions, unique ids, groups, Friday devices, cleanup."""

from __future__ import annotations

import json
import re

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.muslim_prayer_companion import async_remove_config_entry_device
from custom_components.muslim_prayer_companion.const import (
    CONF_ENABLED_GROUPS,
    CONF_FRIDAY_MOSQUES,
    DOMAIN,
    GROUP_FRIDAY,
    GROUP_PRAYER_TIMES,
    SENSOR_GROUPS,
)
from custom_components.muslim_prayer_companion.helpers.settings import Settings
from custom_components.muslim_prayer_companion.sensor import (
    FRIDAY_SENSOR_TYPES,
    SENSOR_TYPES,
    compass_direction,
    expected_unique_ids,
    friday_device_identifier,
)

from .conftest import FIXTURES, FROZEN_NOW, make_entry, setup_entry, state_of

STRINGS = FIXTURES.parent.parent / "custom_components" / "muslim_prayer_companion" / "strings.json"

# Keys shipped since 2.x; their unique_ids ({key}_{entry_id}) must never change.
LEGACY_KEYS = [
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Maghrib",
    "Isha",
    "Midnight",
    "hijri_date",
    "hijri_day",
    "hijri_month_num",
    "hijri_month_readable",
    "hijri_year",
    "hijri_date_readable",
    "hijri_day_month_readable",
    "iqamah_Fajr",
    "iqamah_Dhuhr",
    "iqamah_Asr",
    "iqamah_Maghrib",
    "iqamah_Isha",
    "next_prayer",
    "next_prayer_countdown",
    "next_prayer_minutes",
    "juma_time",
    "current_prayer_period",
    "qibla_direction",
    "location_name",
    "is_ramadan",
    "is_friday",
    "special_night",
]


def test_legacy_keys_still_defined() -> None:
    """Every sensor from 3.0.x still exists with the same key."""
    keys = {description.key for description in SENSOR_TYPES}
    assert set(LEGACY_KEYS) <= keys


def test_every_description_has_a_translated_name() -> None:
    """translation_key is set everywhere and present in strings.json."""
    names = json.loads(STRINGS.read_text(encoding="utf-8"))["entity"]["sensor"]
    for description in (*SENSOR_TYPES, *FRIDAY_SENSOR_TYPES):
        assert description.translation_key, description.key
        assert re.fullmatch(r"[a-z0-9_]+", description.translation_key), description.key
        assert description.translation_key in names, description.key
        assert description.group == GROUP_PRAYER_TIMES or description.group in SENSOR_GROUPS


def test_timestamp_device_classes() -> None:
    """Time sensors are timestamps."""
    for description in SENSOR_TYPES:
        if description.key in (
            "Fajr",
            "Dhuhr",
            "iqamah_Fajr",
            "next_prayer",
            "juma_time",
            "imsak",
            "iftar",
        ):
            assert description.device_class == SensorDeviceClass.TIMESTAMP


def test_compass_direction() -> None:
    """16-point compass."""
    assert compass_direction(0) == "N"
    assert compass_direction(115.5) == "ESE"
    assert compass_direction(348.75) == "N"
    assert compass_direction(348.7) == "NNW"


async def test_registry_matches_expected_unique_ids(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """The entity registry holds exactly the sensors the settings ask for."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)
    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id for e in er.async_entries_for_config_entry(registry, icci_entry.entry_id)
    }
    assert unique_ids == expected_unique_ids(icci_entry.entry_id, Settings.from_entry(icci_entry))
    assert f"friday_icci_jumuah_1_{icci_entry.entry_id}" in unique_ids

    for key in LEGACY_KEYS:
        assert registry.async_get_entity_id("sensor", DOMAIN, f"{key}_{icci_entry.entry_id}")

    state = state_of(hass, icci_entry, "is_friday")
    assert state.state == "false"
    assert state_of(hass, icci_entry, "location_name").state == "ICCI"
    assert state_of(hass, icci_entry, "qibla_direction").attributes["compass_direction"] == "ESE"
    assert state_of(hass, icci_entry, "upcoming_islamic_event").attributes["days_until"] > 0
    assert state_of(hass, icci_entry, "special_night").state == "unknown"


async def test_disabled_groups_create_no_entities(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only prayer-time sensors are created when every group is disabled."""
    freezer.move_to(FROZEN_NOW)
    entry = make_entry(options={CONF_ENABLED_GROUPS: []})
    await setup_entry(hass, entry)
    registry = er.async_get(hass)
    unique_ids = {e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert unique_ids == {
        f"{d.key}_{entry.entry_id}" for d in SENSOR_TYPES if d.group == GROUP_PRAYER_TIMES
    }
    assert not [uid for uid in unique_ids if uid.startswith(("hijri", "friday"))]


async def test_friday_device_and_cleanup_on_reload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Friday mosques get their own device; removing one removes device and entities."""
    freezer.move_to(FROZEN_NOW)
    mosques = [
        {
            "slug": "icci",
            "name": "ICCI",
            "source": "manual",
            "jumuah_1": "13:30",
            "jumuah_2": None,
            "label_1": None,
            "label_2": None,
        },
        {
            "slug": "mai",
            "name": "MAI",
            "source": "manual",
            "jumuah_1": "13:15",
            "jumuah_2": "14:15",
            "label_1": "A",
            "label_2": "B",
        },
    ]
    entry = make_entry(options={CONF_FRIDAY_MOSQUES: mosques})
    await setup_entry(hass, entry)

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    device = dev_reg.async_get_device({(DOMAIN, friday_device_identifier(entry.entry_id, "mai"))})
    assert device is not None
    assert device.name == "MAI"
    assert device.via_device_id == dev_reg.async_get_device({(DOMAIN, entry.entry_id)}).id
    second = ent_reg.async_get_entity_id("sensor", DOMAIN, f"friday_mai_jumuah_2_{entry.entry_id}")
    assert second is not None
    assert hass.states.get(second).state == "2026-10-23T13:15:00+00:00"
    assert hass.states.get(second).attributes["label"] == "B"
    # ICCI has one session: the second sensor exists but is unknown.
    icci_second = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"friday_icci_jumuah_2_{entry.entry_id}"
    )
    assert hass.states.get(icci_second).state == "unknown"

    # Remove MAI from the options and reload: its device and sensors disappear.
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_FRIDAY_MOSQUES: mosques[:1]}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        dev_reg.async_get_device({(DOMAIN, friday_device_identifier(entry.entry_id, "mai"))})
        is None
    )
    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, f"friday_mai_jumuah_1_{entry.entry_id}")
        is None
    )
    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, f"friday_icci_jumuah_1_{entry.entry_id}")
        is not None
    )

    # Disable the Friday group: the legacy juma_time and the remaining device go too.
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_ENABLED_GROUPS: [g for g in SENSOR_GROUPS if g != GROUP_FRIDAY],
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, f"juma_time_{entry.entry_id}") is None
    assert (
        dev_reg.async_get_device({(DOMAIN, friday_device_identifier(entry.entry_id, "icci"))})
        is None
    )
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, f"Fajr_{entry.entry_id}") is not None


async def test_remove_friday_device_from_ui(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hicc_entry: MockConfigEntry,
    mock_mosque_sites: object,
) -> None:
    """Deleting a Friday device removes the mosque from the options."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, hicc_entry)

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        {(DOMAIN, friday_device_identifier(hicc_entry.entry_id, "hicc"))}
    )
    assert device is not None
    assert await async_remove_config_entry_device(hass, hicc_entry, device) is True
    await hass.async_block_till_done()
    assert hicc_entry.options[CONF_FRIDAY_MOSQUES] == []

    main_device = dev_reg.async_get_device({(DOMAIN, hicc_entry.entry_id)})
    assert main_device is not None
    assert await async_remove_config_entry_device(hass, hicc_entry, main_device) is False


@pytest.mark.parametrize("key", ["hijri_month_num", "next_prayer_minutes", "days_until_ramadan"])
async def test_numeric_sensors_are_numeric(
    hass: HomeAssistant, icci_entry: MockConfigEntry, freezer: FrozenDateTimeFactory, key: str
) -> None:
    """Numeric sensors have numeric states."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, icci_entry)
    float(state_of(hass, icci_entry, key).state)
