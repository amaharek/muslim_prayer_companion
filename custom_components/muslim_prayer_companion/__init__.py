"""
Custom component to get Muslim Prayer Companion.

For more details about this component, please refer to the documentation at
https://github.com/amaharek/muslim_prayer_companion
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import (
    CONF_CALC_METHOD,
    CONF_ENABLED_GROUPS,
    CONF_FRIDAY_MOSQUES,
    CONF_FRIDAY_SLUG,
    CONF_IQAMAH_METHOD,
    CONF_IQAMAH_OFFSETS,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    CONFIG_VERSION,
    DEFAULT_CALC_METHOD,
    DEFAULT_LOCATION_NAME,
    DOMAIN,
    GROUP_COUNTDOWN,
    GROUP_HIJRI,
    IQAMAH_METHOD_DISABLED,
    IQAMAH_METHOD_MOSQUE,
    IQAMAH_METHOD_OFFSET,
    LOGGER,
    PRAYERS,
    SERVICE_GET_PRAYER_TIMES,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
    STANDARD_CALC_METHODS,
)
from .coordinator import MuslimPrayerCompanionDataUpdateCoordinator, fallback_issue_id
from .helpers.registry import get_mosque, is_mosque_key
from .helpers.settings import default_iqamah_method, default_options, entry_unique_id

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

MAX_SERVICE_DAYS = 366
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Optional("date"): cv.date,
        vol.Optional("days", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_SERVICE_DAYS)
        ),
    }
)


@dataclass
class MuslimPrayerCompanionData:
    """Runtime data for Muslim Prayer Companion."""

    coordinator: MuslimPrayerCompanionDataUpdateCoordinator


type MuslimPrayerCompanionConfigEntry = ConfigEntry[MuslimPrayerCompanionData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001
    """Register the integration's actions."""
    if not hass.services.has_service(DOMAIN, SERVICE_GET_PRAYER_TIMES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_PRAYER_TIMES,
            _async_get_prayer_times_service,
            schema=SERVICE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    return True


def _loaded_entries(hass: HomeAssistant) -> list[MuslimPrayerCompanionConfigEntry]:
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None
    ]


async def _async_get_prayer_times_service(call: ServiceCall) -> ServiceResponse:
    """Return prayer times for one or more days as a service response."""
    hass = call.hass
    entries = _loaded_entries(hass)
    entry_id = call.data.get("config_entry_id")
    if entry_id:
        entry = next((e for e in entries if e.entry_id == entry_id), None)
        if entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
                translation_placeholders={"entry_id": entry_id},
            )
    elif entries:
        entry = entries[0]
    else:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_entries")

    coordinator = entry.runtime_data.coordinator
    start: date = call.data.get("date") or dt_util.now(coordinator.tz).date()
    days: list[dict[str, Any]] = []
    for offset in range(call.data["days"]):
        day = start + timedelta(days=offset)
        times = await coordinator.async_prayer_times_for(day)
        entry_times = {key: value.isoformat() for key, value in times.to_dict().items()}
        days.append({"date": day.isoformat(), **entry_times, "source": times.source})
    return {
        "location_name": coordinator.location_name,
        "provider": coordinator.provider_name,
        "days": days,
    }


async def async_setup_entry(hass: HomeAssistant, entry: MuslimPrayerCompanionConfigEntry) -> bool:
    """Set up Muslim Prayer Companion from a config entry."""
    LOGGER.debug("Setting up Muslim Prayer Companion entry: %s", entry.entry_id)

    coordinator = MuslimPrayerCompanionDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = MuslimPrayerCompanionData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    LOGGER.debug("Muslim Prayer Companion set up for %s", coordinator.location_name)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MuslimPrayerCompanionConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.async_shutdown()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up when an entry is deleted."""
    ir.async_delete_issue(hass, DOMAIN, fallback_issue_id(entry.entry_id))


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: MuslimPrayerCompanionConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow deleting a Friday-mosque device: it removes that mosque from the options."""
    prefix = f"{entry.entry_id}_friday_"
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN or not identifier.startswith(prefix):
            continue
        slug = identifier[len(prefix) :]
        mosques = [
            item
            for item in entry.options.get(CONF_FRIDAY_MOSQUES, [])
            if item.get(CONF_FRIDAY_SLUG) != slug
        ]
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_FRIDAY_MOSQUES: mosques}
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return True
    return False


# --- Migration ---------------------------------------------------------------


def migrate_options(
    data: dict[str, Any], old_options: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Return the version 3 ``(data, options)`` for a version 1 or 2 entry.

    Pure, so it can be unit-tested without Home Assistant.
    """
    data = dict(data)
    options = dict(old_options)

    # 3.0.x read the method from options first, so that is what users actually ran.
    effective = options.pop(CONF_CALC_METHOD, data.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD))
    if is_mosque_key(effective):
        source_type = SOURCE_IRELAND
        method = effective
    else:
        source_type = SOURCE_CALCULATED
        method = effective if effective in STANDARD_CALC_METHODS else DEFAULT_CALC_METHOD
    data[CONF_SOURCE_TYPE] = source_type
    data[CONF_CALC_METHOD] = method
    mosque_key = method if source_type == SOURCE_IRELAND else None

    new_options = default_options(source_type, method)

    # Previously stored but never applied toggles become sensor groups.
    enable_hijri = options.pop("enable_hijri", True)
    enable_countdown = options.pop("enable_countdown", True)
    groups = list(new_options[CONF_ENABLED_GROUPS])
    if enable_hijri is False and GROUP_HIJRI in groups:
        groups.remove(GROUP_HIJRI)
    if enable_countdown is False and GROUP_COUNTDOWN in groups:
        groups.remove(GROUP_COUNTDOWN)
    new_options[CONF_ENABLED_GROUPS] = groups

    old_iqamah = options.pop(CONF_IQAMAH_METHOD, None)
    if old_iqamah == IQAMAH_METHOD_DISABLED:
        new_options[CONF_IQAMAH_METHOD] = IQAMAH_METHOD_DISABLED
    elif old_iqamah == IQAMAH_METHOD_OFFSET and (
        default_iqamah_method(mosque_key) != IQAMAH_METHOD_MOSQUE
    ):
        new_options[CONF_IQAMAH_METHOD] = IQAMAH_METHOD_OFFSET

    old_offsets = options.pop(CONF_IQAMAH_OFFSETS, None)
    if isinstance(old_offsets, dict):
        for prayer in PRAYERS:
            try:
                new_options[CONF_IQAMAH_OFFSETS][prayer] = int(old_offsets[prayer])
            except (KeyError, TypeError, ValueError):
                continue

    # Keep any other option a newer version may already have written.
    for key, value in options.items():
        new_options.setdefault(key, value)

    return data, new_options


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a config entry to the current version."""
    LOGGER.debug(
        "Migrating config entry %s from version %s to %s",
        entry.entry_id,
        entry.version,
        CONFIG_VERSION,
    )
    if entry.version > CONFIG_VERSION:
        return False
    if entry.version == CONFIG_VERSION:
        return True

    data, options = migrate_options(dict(entry.data), dict(entry.options))

    # Location defaults (version 1 entries had none); never overwrite stored ones.
    data.setdefault(CONF_LATITUDE, hass.config.latitude)
    data.setdefault(CONF_LONGITUDE, hass.config.longitude)
    data.setdefault(CONF_TIMEZONE, str(hass.config.time_zone))
    if not data.get(CONF_LOCATION_NAME):
        data[CONF_LOCATION_NAME] = (
            get_mosque(data[CONF_CALC_METHOD]).short_name
            if data[CONF_SOURCE_TYPE] == SOURCE_IRELAND
            else DEFAULT_LOCATION_NAME
        )

    updates: dict[str, Any] = {"data": data, "options": options, "version": CONFIG_VERSION}
    if entry.unique_id is None:
        unique_id = entry_unique_id(
            data[CONF_SOURCE_TYPE],
            data[CONF_CALC_METHOD],
            data[CONF_LATITUDE],
            data[CONF_LONGITUDE],
        )
        other = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, unique_id)
        if other is not None and other.entry_id != entry.entry_id:
            LOGGER.warning(
                "Config entry %s duplicates %s (%s); leaving it without a unique id",
                entry.title,
                other.title,
                unique_id,
            )
        else:
            updates["unique_id"] = unique_id

    hass.config_entries.async_update_entry(entry, **updates)
    LOGGER.info(
        "Migrated %s to version %s (%s, %s)",
        entry.title,
        CONFIG_VERSION,
        data[CONF_SOURCE_TYPE],
        data[CONF_CALC_METHOD],
    )
    return True
