"""
Custom component to get Muslim Prayer Companion.

For more details about this component, please refer to the documentation at
https://github.com/amaharek/muslim_prayer_companion
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CALC_METHOD,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    CONFIG_VERSION,
    DEFAULT_CALC_METHOD,
    DEFAULT_LOCATION_NAME,
    DEFAULT_SOURCE_TYPE,
    DOMAIN,
    IRELAND_CALC_METHODS,
    LOGGER,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
)
from .coordinator import MuslimPrayerCompanionDataUpdateCoordinator

if TYPE_CHECKING:
    pass

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


@dataclass
class MuslimPrayerCompanionData:
    """Runtime data for Muslim Prayer Companion."""

    coordinator: MuslimPrayerCompanionDataUpdateCoordinator


type MuslimPrayerCompanionConfigEntry = ConfigEntry[MuslimPrayerCompanionData]


async def async_setup_entry(
    hass: HomeAssistant, entry: MuslimPrayerCompanionConfigEntry
) -> bool:
    """Set up the Muslim Prayer Companion from a config entry.

    Supports multiple config entries for multi-mosque/multi-location functionality.
    """
    LOGGER.debug("Setting up Muslim Prayer Companion entry: %s", entry.entry_id)

    # Create coordinator with entry-specific configuration
    coordinator = MuslimPrayerCompanionDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        latitude=entry.data.get(CONF_LATITUDE),
        longitude=entry.data.get(CONF_LONGITUDE),
        location_name=entry.data.get(CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME),
    )

    # Perform first refresh
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in entry runtime data (supports multi-instance)
    entry.runtime_data = MuslimPrayerCompanionData(coordinator=coordinator)

    # Set up update listener for options
    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    # Forward to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.info(
        "Muslim Prayer Companion set up for %s",
        entry.data.get(CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME),
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MuslimPrayerCompanionConfigEntry
) -> bool:
    """Unload Muslim Prayer entry from config_entry."""
    LOGGER.debug("Unloading Muslim Prayer Companion entry: %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up coordinator
        coordinator = entry.runtime_data.coordinator
        await coordinator.async_shutdown()

    return unload_ok


async def async_options_updated(
    hass: HomeAssistant, entry: MuslimPrayerCompanionConfigEntry
) -> None:
    """Triggered by config entry options updates."""
    LOGGER.debug("Options updated for entry: %s", entry.entry_id)

    coordinator = entry.runtime_data.coordinator

    # Cancel scheduled update
    if coordinator.event_unsub:
        coordinator.event_unsub()

    # Reset provider to pick up new calculation method
    coordinator._provider = None

    # Request refresh
    await coordinator.async_request_refresh()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version.

    Migration from VERSION 1 to 2:
    - Add latitude/longitude from HA config
    - Add location_name
    - Add source_type
    - Preserve calculation_method and other settings
    """
    LOGGER.debug(
        "Migrating config entry from version %s to %s",
        entry.version,
        CONFIG_VERSION,
    )

    if entry.version == 1:
        # Get current calculation method
        calc_method = entry.data.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)

        # Determine source type from calculation method
        if calc_method in IRELAND_CALC_METHODS.values():
            source_type = SOURCE_IRELAND
        else:
            source_type = SOURCE_CALCULATED

        # Build new data with location from HA config
        new_data = {
            **entry.data,
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
            CONF_LOCATION_NAME: DEFAULT_LOCATION_NAME,
            CONF_SOURCE_TYPE: source_type,
            CONF_TIMEZONE: str(hass.config.time_zone),
        }

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            version=CONFIG_VERSION,
        )

        LOGGER.info(
            "Migration complete: Added location (%s, %s) and source type '%s'",
            hass.config.latitude,
            hass.config.longitude,
            source_type,
        )

    return True
