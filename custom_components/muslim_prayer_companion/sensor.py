"""Platform to retrieve Muslim Prayer Companion information for Home Assistant."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import parse_datetime

from .const import CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME, DOMAIN, LOGGER, NAME

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import MuslimPrayerCompanionConfigEntry
    from .coordinator import MuslimPrayerCompanionDataUpdateCoordinator


# Define sensor types - backward compatible keys preserved
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    # Prayer Times (original sensors - backward compatible)
    SensorEntityDescription(
        key="Fajr",
        name="Fajr Prayer",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-up",
    ),
    SensorEntityDescription(
        key="Sunrise",
        name="Sunrise Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunny",
    ),
    SensorEntityDescription(
        key="Dhuhr",
        name="Dhuhr Prayer",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunny",
    ),
    SensorEntityDescription(
        key="Asr",
        name="Asr Prayer",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunny-off",
    ),
    SensorEntityDescription(
        key="Maghrib",
        name="Maghrib Prayer",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-down",
    ),
    SensorEntityDescription(
        key="Isha",
        name="Isha Prayer",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-night",
    ),
    SensorEntityDescription(
        key="Midnight",
        name="Midnight Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
    # Hijri Date Information (original sensors - backward compatible)
    SensorEntityDescription(
        key="hijri_date",
        name="Hijri Date",
        icon="mdi:calendar-islamic",
    ),
    SensorEntityDescription(
        key="hijri_day",
        name="Hijri Day",
        icon="mdi:calendar-today",
    ),
    SensorEntityDescription(
        key="hijri_month_num",
        name="Hijri Month Number",
        icon="mdi:calendar-month",
    ),
    SensorEntityDescription(
        key="hijri_month_readable",
        name="Hijri Month",
        icon="mdi:calendar-month",
    ),
    SensorEntityDescription(
        key="hijri_year",
        name="Hijri Year",
        icon="mdi:calendar",
    ),
    SensorEntityDescription(
        key="hijri_date_readable",
        name="Hijri Date Readable",
        icon="mdi:calendar-islamic",
    ),
    SensorEntityDescription(
        key="hijri_day_month_readable",
        name="Hijri Day and Month",
        icon="mdi:calendar-islamic",
    ),
    # Iqamah Times (original sensors - backward compatible)
    SensorEntityDescription(
        key="iqamah_Fajr",
        name="Iqamah Fajr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
    ),
    SensorEntityDescription(
        key="iqamah_Dhuhr",
        name="Iqamah Dhuhr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
    ),
    SensorEntityDescription(
        key="iqamah_Asr",
        name="Iqamah Asr",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
    ),
    SensorEntityDescription(
        key="iqamah_Maghrib",
        name="Iqamah Maghrib",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
    ),
    SensorEntityDescription(
        key="iqamah_Isha",
        name="Iqamah Isha",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
    ),
    # Next Prayer Sensor (original - backward compatible)
    SensorEntityDescription(
        key="next_prayer",
        name="Next Prayer",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-alert",
    ),
    # NEW SENSORS - Phase 4 additions
    # Countdown sensors
    SensorEntityDescription(
        key="next_prayer_countdown",
        name="Next Prayer Countdown",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="next_prayer_minutes",
        name="Next Prayer Minutes",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        icon="mdi:timer-sand",
    ),
    # Friday prayer sensors
    SensorEntityDescription(
        key="juma_time",
        name="Jumu'a Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:mosque",
    ),
    # Prayer period sensor
    SensorEntityDescription(
        key="current_prayer_period",
        name="Current Prayer Period",
        icon="mdi:clock-time-eight",
    ),
    # Qibla direction
    SensorEntityDescription(
        key="qibla_direction",
        name="Qibla Direction",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:compass",
    ),
    # Location info
    SensorEntityDescription(
        key="location_name",
        name="Location",
        icon="mdi:map-marker",
    ),
    # Special dates
    SensorEntityDescription(
        key="is_ramadan",
        name="Is Ramadan",
        icon="mdi:moon-waning-crescent",
    ),
    SensorEntityDescription(
        key="is_friday",
        name="Is Friday",
        icon="mdi:calendar-week",
    ),
    SensorEntityDescription(
        key="special_night",
        name="Special Night",
        icon="mdi:star-crescent",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MuslimPrayerCompanionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Muslim Prayer Companion sensor platform."""
    # Get coordinator from entry runtime data (multi-instance support)
    coordinator = config_entry.runtime_data.coordinator

    # Create sensors
    entities = [
        MuslimPrayerCompanionTimeSensor(coordinator, description, config_entry)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)

    LOGGER.debug(
        "Set up %d sensors for %s",
        len(entities),
        config_entry.data.get(CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME),
    )


class MuslimPrayerCompanionTimeSensor(
    CoordinatorEntity[MuslimPrayerCompanionDataUpdateCoordinator], SensorEntity
):
    """Representation of a Muslim Prayer Companion sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MuslimPrayerCompanionDataUpdateCoordinator,
        description: SensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        # IMPORTANT: Preserve backward compatible unique_id format
        # Original format: {key}_{entry_id}
        self._attr_unique_id = f"{description.key}_{config_entry.entry_id}"

        # Device info groups all sensors under one device per config entry
        location_name = config_entry.data.get(CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"{NAME} - {location_name}",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Muslim Prayer Companion",
            model="Prayer Times",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            # Don't log error for optional sensors that may not be present
            if self.entity_description.key not in (
                "juma_time",
                "special_night",
                "Midnight",
            ):
                LOGGER.debug("No value found for %s", self.entity_description.key)
            return None

        # Handle TIMESTAMP device class
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if isinstance(value, datetime):
                return value
            elif isinstance(value, str):
                return parse_datetime(value)
            else:
                LOGGER.warning(
                    "Unexpected type for %s: %s",
                    self.entity_description.key,
                    type(value),
                )
                return None

        # Handle boolean values (convert to string for HA)
        if isinstance(value, bool):
            return "true" if value else "false"

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes for the sensor."""
        attrs: dict[str, Any] = {}

        # For the "next_prayer" sensor, add the prayer name
        if self.entity_description.key == "next_prayer":
            next_prayer_name = self.coordinator.data.get("next_prayer_name")
            if next_prayer_name:
                attrs["prayer"] = next_prayer_name

        # For qibla sensor, add compass direction
        if self.entity_description.key == "qibla_direction":
            qibla_degrees = self.coordinator.data.get("qibla_direction")
            if qibla_degrees is not None:
                attrs["compass_direction"] = self._get_compass_direction(qibla_degrees)

        # For hijri date sensors, add additional context
        if self.entity_description.key == "hijri_date_readable":
            attrs["is_ramadan"] = self.coordinator.data.get("is_ramadan", False)

        return attrs

    @staticmethod
    def _get_compass_direction(degrees: float) -> str:
        """Convert degrees to compass direction."""
        directions = [
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
        ]
        index = round(degrees / 22.5) % 16
        return directions[index]

    @property
    def available(self) -> bool:
        """Return True if sensor is available."""
        # Base availability from coordinator
        if not super().available:
            return False

        # Some sensors may not always have data
        if self.entity_description.key in ("juma_time",):
            # juma_time only available on Fridays
            return self.coordinator.data.get("is_friday", False)

        return True
