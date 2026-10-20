"""Sensor platform for Muslim Prayer Companion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import parse_datetime

from .const import (
    ATTR_SOURCE,
    DOMAIN,
    GROUP_COUNTDOWN,
    GROUP_FRIDAY,
    GROUP_HIJRI,
    GROUP_IQAMAH,
    GROUP_PRAYER_TIMES,
    GROUP_QIBLA,
    GROUP_SPECIAL_DATES,
    LOGGER,
    NAME,
)
from .coordinator import MuslimPrayerCompanionDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import MuslimPrayerCompanionConfigEntry
    from .helpers.friday import FridayMosqueConfig
    from .helpers.settings import Settings


@dataclass(frozen=True, kw_only=True)
class MuslimPrayerSensorEntityDescription(SensorEntityDescription):
    """Sensor description with the settings group it belongs to."""

    group: str = GROUP_PRAYER_TIMES


# Keys (and therefore unique_ids) are unchanged since 2.x: {key}_{entry_id}.
SENSOR_TYPES: tuple[MuslimPrayerSensorEntityDescription, ...] = (
    # Prayer times (always on)
    MuslimPrayerSensorEntityDescription(
        key="Fajr",
        translation_key="fajr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-up",
    ),
    MuslimPrayerSensorEntityDescription(
        key="Sunrise",
        translation_key="sunrise",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunny",
    ),
    MuslimPrayerSensorEntityDescription(
        key="Dhuhr",
        translation_key="dhuhr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunny",
    ),
    MuslimPrayerSensorEntityDescription(
        key="Asr",
        translation_key="asr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunny-off",
    ),
    MuslimPrayerSensorEntityDescription(
        key="Maghrib",
        translation_key="maghrib",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-down",
    ),
    MuslimPrayerSensorEntityDescription(
        key="Isha",
        translation_key="isha",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-night",
    ),
    MuslimPrayerSensorEntityDescription(
        key="Midnight",
        translation_key="midnight",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
    MuslimPrayerSensorEntityDescription(
        key="next_prayer",
        translation_key="next_prayer",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-alert",
    ),
    MuslimPrayerSensorEntityDescription(
        key="current_prayer_period",
        translation_key="current_prayer_period",
        icon="mdi:clock-time-eight",
    ),
    MuslimPrayerSensorEntityDescription(
        key="location_name",
        translation_key="location_name",
        icon="mdi:map-marker",
    ),
    # Countdown
    MuslimPrayerSensorEntityDescription(
        key="next_prayer_countdown",
        translation_key="next_prayer_countdown",
        icon="mdi:timer-outline",
        group=GROUP_COUNTDOWN,
    ),
    MuslimPrayerSensorEntityDescription(
        key="next_prayer_minutes",
        translation_key="next_prayer_minutes",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-sand",
        group=GROUP_COUNTDOWN,
    ),
    # Hijri date
    MuslimPrayerSensorEntityDescription(
        key="hijri_date",
        translation_key="hijri_date",
        icon="mdi:calendar-islamic",
        group=GROUP_HIJRI,
    ),
    MuslimPrayerSensorEntityDescription(
        key="hijri_day",
        translation_key="hijri_day",
        icon="mdi:calendar-today",
        group=GROUP_HIJRI,
    ),
    MuslimPrayerSensorEntityDescription(
        key="hijri_month_num",
        translation_key="hijri_month_number",
        icon="mdi:calendar-month",
        group=GROUP_HIJRI,
    ),
    MuslimPrayerSensorEntityDescription(
        key="hijri_month_readable",
        translation_key="hijri_month",
        icon="mdi:calendar-month",
        group=GROUP_HIJRI,
    ),
    MuslimPrayerSensorEntityDescription(
        key="hijri_year",
        translation_key="hijri_year",
        icon="mdi:calendar",
        group=GROUP_HIJRI,
    ),
    MuslimPrayerSensorEntityDescription(
        key="hijri_date_readable",
        translation_key="hijri_date_readable",
        icon="mdi:calendar-islamic",
        group=GROUP_HIJRI,
    ),
    MuslimPrayerSensorEntityDescription(
        key="hijri_day_month_readable",
        translation_key="hijri_day_month",
        icon="mdi:calendar-islamic",
        group=GROUP_HIJRI,
    ),
    # Iqamah
    MuslimPrayerSensorEntityDescription(
        key="iqamah_Fajr",
        translation_key="iqamah_fajr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
        group=GROUP_IQAMAH,
    ),
    MuslimPrayerSensorEntityDescription(
        key="iqamah_Dhuhr",
        translation_key="iqamah_dhuhr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
        group=GROUP_IQAMAH,
    ),
    MuslimPrayerSensorEntityDescription(
        key="iqamah_Asr",
        translation_key="iqamah_asr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
        group=GROUP_IQAMAH,
    ),
    MuslimPrayerSensorEntityDescription(
        key="iqamah_Maghrib",
        translation_key="iqamah_maghrib",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
        group=GROUP_IQAMAH,
    ),
    MuslimPrayerSensorEntityDescription(
        key="iqamah_Isha",
        translation_key="iqamah_isha",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
        group=GROUP_IQAMAH,
    ),
    # Qibla
    MuslimPrayerSensorEntityDescription(
        key="qibla_direction",
        translation_key="qibla_direction",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:compass",
        group=GROUP_QIBLA,
    ),
    # Special dates
    MuslimPrayerSensorEntityDescription(
        key="is_ramadan",
        translation_key="is_ramadan",
        icon="mdi:moon-waning-crescent",
        group=GROUP_SPECIAL_DATES,
    ),
    MuslimPrayerSensorEntityDescription(
        key="is_friday",
        translation_key="is_friday",
        icon="mdi:calendar-week",
        group=GROUP_SPECIAL_DATES,
    ),
    MuslimPrayerSensorEntityDescription(
        key="special_night",
        translation_key="special_night",
        icon="mdi:star-crescent",
        group=GROUP_SPECIAL_DATES,
    ),
    MuslimPrayerSensorEntityDescription(
        key="ramadan_day",
        translation_key="ramadan_day",
        icon="mdi:calendar-star",
        group=GROUP_SPECIAL_DATES,
    ),
    MuslimPrayerSensorEntityDescription(
        key="days_until_ramadan",
        translation_key="days_until_ramadan",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar-clock",
        group=GROUP_SPECIAL_DATES,
    ),
    MuslimPrayerSensorEntityDescription(
        key="upcoming_islamic_event",
        translation_key="upcoming_islamic_event",
        icon="mdi:calendar-heart",
        group=GROUP_SPECIAL_DATES,
    ),
    MuslimPrayerSensorEntityDescription(
        key="imsak",
        translation_key="imsak",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:food-off",
        group=GROUP_SPECIAL_DATES,
    ),
    MuslimPrayerSensorEntityDescription(
        key="iftar",
        translation_key="iftar",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:food",
        group=GROUP_SPECIAL_DATES,
    ),
    # Friday (legacy alias, kept for compatibility)
    MuslimPrayerSensorEntityDescription(
        key="juma_time",
        translation_key="juma_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
        group=GROUP_FRIDAY,
    ),
)

FRIDAY_SENSOR_TYPES: tuple[MuslimPrayerSensorEntityDescription, ...] = tuple(
    MuslimPrayerSensorEntityDescription(
        key=f"jumuah_{session}",
        translation_key=f"friday_jumuah_{session}",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
        group=GROUP_FRIDAY,
    )
    for session in (1, 2)
)

SOURCE_ATTRIBUTE_KEYS = {
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Maghrib",
    "Isha",
    "Midnight",
    "next_prayer",
    "imsak",
    "iftar",
}

COMPASS_DIRECTIONS = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)
DEGREES_PER_DIRECTION = 22.5


def compass_direction(degrees: float) -> str:
    """Convert a bearing in degrees to a 16-point compass direction."""
    return COMPASS_DIRECTIONS[round(degrees / DEGREES_PER_DIRECTION) % len(COMPASS_DIRECTIONS)]


def friday_device_identifier(entry_id: str, slug: str) -> str:
    """Return the device identifier of a Friday mosque."""
    return f"{entry_id}_friday_{slug}"


def friday_unique_id(entry_id: str, slug: str, session: int) -> str:
    """Return the unique_id of a Friday sensor."""
    return f"friday_{slug}_jumuah_{session}_{entry_id}"


def static_descriptions(settings: Settings) -> list[MuslimPrayerSensorEntityDescription]:
    """Return the fixed sensors enabled by the settings."""
    return [
        description
        for description in SENSOR_TYPES
        if description.group == GROUP_PRAYER_TIMES or description.group in settings.enabled_groups
    ]


def expected_unique_ids(entry_id: str, settings: Settings) -> set[str]:
    """Return every sensor unique_id this entry should currently have."""
    expected = {f"{description.key}_{entry_id}" for description in static_descriptions(settings)}
    if GROUP_FRIDAY in settings.enabled_groups:
        for mosque in settings.friday_mosques:
            expected.update(friday_unique_id(entry_id, mosque.slug, s) for s in (1, 2))
    return expected


@callback
def _async_cleanup_stale(
    hass: HomeAssistant, entry: ConfigEntry, settings: Settings, expected: set[str]
) -> None:
    """Remove sensors and Friday devices that the current settings no longer create."""
    ent_reg = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.domain == "sensor" and reg_entry.unique_id not in expected:
            LOGGER.debug("Removing stale entity %s", reg_entry.entity_id)
            ent_reg.async_remove(reg_entry.entity_id)

    friday_enabled = GROUP_FRIDAY in settings.enabled_groups
    current = {friday_device_identifier(entry.entry_id, m.slug) for m in settings.friday_mosques}
    prefix = f"{entry.entry_id}_friday_"
    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN or not identifier.startswith(prefix):
                continue
            if not friday_enabled or identifier not in current:
                LOGGER.debug("Removing stale Friday device %s", identifier)
                dev_reg.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MuslimPrayerCompanionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Muslim Prayer Companion sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    settings = coordinator.settings

    _async_cleanup_stale(
        hass, config_entry, settings, expected_unique_ids(config_entry.entry_id, settings)
    )

    entities: list[SensorEntity] = [
        MuslimPrayerCompanionTimeSensor(coordinator, description, config_entry)
        for description in static_descriptions(settings)
    ]
    if GROUP_FRIDAY in settings.enabled_groups:
        entities.extend(
            MuslimPrayerCompanionFridaySensor(coordinator, description, config_entry, mosque)
            for mosque in settings.friday_mosques
            for description in FRIDAY_SENSOR_TYPES
        )

    async_add_entities(entities)
    LOGGER.debug("Set up %d sensors for %s", len(entities), coordinator.location_name)


class MuslimPrayerCompanionTimeSensor(
    CoordinatorEntity[MuslimPrayerCompanionDataUpdateCoordinator], SensorEntity
):
    """A sensor fed from the coordinator data dict."""

    _attr_has_entity_name = True
    entity_description: MuslimPrayerSensorEntityDescription

    def __init__(
        self,
        coordinator: MuslimPrayerCompanionDataUpdateCoordinator,
        description: MuslimPrayerSensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # Backward compatible unique_id format: {key}_{entry_id}
        self._attr_unique_id = f"{description.key}_{config_entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"{NAME} - {coordinator.location_name}",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=NAME,
            model="Prayer times",
        )

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    def _raw_value(self) -> Any:
        return self._data.get(self.entity_description.key)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        value = self._raw_value()
        if value is None:
            return None

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return parse_datetime(value)
            LOGGER.warning("Unexpected type for %s: %s", self.entity_description.key, type(value))
            return None

        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, date):
            return value.isoformat()
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes for the sensor."""
        attrs: dict[str, Any] = {}
        key = self.entity_description.key
        data = self._data

        if key in SOURCE_ATTRIBUTE_KEYS:
            attrs[ATTR_SOURCE] = data.get("source")
        if key.startswith("iqamah_"):
            attrs[ATTR_SOURCE] = data.get("iqamah_source")
        if key == "next_prayer" and data.get("next_prayer_name"):
            attrs["prayer"] = data["next_prayer_name"]
        if key == "qibla_direction" and data.get("qibla_direction") is not None:
            attrs["compass_direction"] = compass_direction(data["qibla_direction"])
        if key == "hijri_date_readable":
            attrs["is_ramadan"] = data.get("is_ramadan", False)
        if key == "upcoming_islamic_event":
            event_date = data.get("upcoming_islamic_event_date")
            attrs["date"] = event_date.isoformat() if isinstance(event_date, date) else None
            attrs["days_until"] = data.get("upcoming_islamic_event_days")
        if key == "juma_time":
            attrs[ATTR_SOURCE] = data.get("source")
        return attrs


class MuslimPrayerCompanionFridaySensor(MuslimPrayerCompanionTimeSensor):
    """Jumu'ah time of one Friday mosque, under its own device."""

    def __init__(
        self,
        coordinator: MuslimPrayerCompanionDataUpdateCoordinator,
        description: MuslimPrayerSensorEntityDescription,
        config_entry: ConfigEntry,
        mosque: FridayMosqueConfig,
    ) -> None:
        """Initialize the Friday sensor."""
        super().__init__(coordinator, description, config_entry)
        self._mosque = mosque
        session = int(description.key.rsplit("_", 1)[1])
        self._attr_unique_id = friday_unique_id(config_entry.entry_id, mosque.slug, session)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, friday_device_identifier(config_entry.entry_id, mosque.slug))},
            name=mosque.name,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=NAME,
            model="Friday prayers",
            via_device=(DOMAIN, config_entry.entry_id),
        )

    @property
    def _mosque_data(self) -> dict[str, Any] | None:
        return (self._data.get("friday") or {}).get(self._mosque.slug)

    def _raw_value(self) -> Any:
        info = self._mosque_data
        return info.get(self.entity_description.key) if info else None

    @property
    def available(self) -> bool:
        """Available while the mosque is configured and the coordinator is healthy."""
        return super().available and self._mosque_data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return mosque name, label and where the time came from."""
        info = self._mosque_data or {}
        session = int(self.entity_description.key.rsplit("_", 1)[1])
        labels = info.get("labels") or []
        return {
            "mosque_name": self._mosque.name,
            "label": labels[session - 1] if len(labels) >= session else None,
            ATTR_SOURCE: info.get("source", self._mosque.source),
            "times_from": info.get("times_from"),
        }
