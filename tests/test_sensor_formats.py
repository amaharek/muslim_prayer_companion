"""Test cases for sensor value formats."""

import re
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass

from custom_components.muslim_prayer_companion.sensor import (
    SENSOR_TYPES,
    MuslimPrayerCompanionTimeSensor,
)


class TestSensorTypeDefinitions:
    """Test sensor type definitions."""

    def test_all_original_sensors_preserved(self):
        """All original sensors should still be defined."""
        original_keys = [
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
        ]

        sensor_keys = [s.key for s in SENSOR_TYPES]

        for key in original_keys:
            assert key in sensor_keys, f"Original sensor '{key}' missing"

    def test_new_sensors_added(self):
        """New Phase 4 sensors should be defined."""
        new_keys = [
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

        sensor_keys = [s.key for s in SENSOR_TYPES]

        for key in new_keys:
            assert key in sensor_keys, f"New sensor '{key}' not found"

    def test_prayer_time_sensors_have_timestamp_class(self):
        """Prayer time sensors should have TIMESTAMP device class."""
        prayer_keys = [
            "Fajr",
            "Sunrise",
            "Dhuhr",
            "Asr",
            "Maghrib",
            "Isha",
            "next_prayer",
        ]

        for sensor in SENSOR_TYPES:
            if sensor.key in prayer_keys:
                assert (
                    sensor.device_class == SensorDeviceClass.TIMESTAMP
                ), f"Sensor '{sensor.key}' should have TIMESTAMP device class"

    def test_iqamah_sensors_have_timestamp_class(self):
        """Iqamah sensors should have TIMESTAMP device class."""
        iqamah_keys = [
            "iqamah_Fajr",
            "iqamah_Dhuhr",
            "iqamah_Asr",
            "iqamah_Maghrib",
            "iqamah_Isha",
        ]

        for sensor in SENSOR_TYPES:
            if sensor.key in iqamah_keys:
                assert (
                    sensor.device_class == SensorDeviceClass.TIMESTAMP
                ), f"Sensor '{sensor.key}' should have TIMESTAMP device class"


class TestSensorValueFormats:
    """Test sensor value formats match expected patterns."""

    @pytest.fixture
    def mock_coordinator(self) -> MagicMock:
        """Create mock coordinator with sample data."""
        coordinator = MagicMock()
        coordinator.data = {
            # Prayer times (UTC datetime)
            "Fajr": datetime(2024, 1, 15, 6, 30, tzinfo=timezone.utc),
            "Sunrise": datetime(2024, 1, 15, 8, 15, tzinfo=timezone.utc),
            "Dhuhr": datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc),
            "Asr": datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc),
            "Maghrib": datetime(2024, 1, 15, 17, 30, tzinfo=timezone.utc),
            "Isha": datetime(2024, 1, 15, 19, 0, tzinfo=timezone.utc),
            # Hijri date (strings)
            "hijri_date": "15-07-1445",
            "hijri_day": "15",
            "hijri_month_num": 7,
            "hijri_month_readable": "Rajab",
            "hijri_year": "1445",
            "hijri_date_readable": "15-Rajab-1445",
            "hijri_day_month_readable": "15-Rajab",
            # Next prayer
            "next_prayer": datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc),
            "next_prayer_name": "Asr",
            "next_prayer_minutes": 45,
            "next_prayer_countdown": "Asr in 45 minutes",
            # Qibla
            "qibla_direction": 119.5,
            # Special dates
            "is_ramadan": False,
            "is_friday": True,
            "special_night": "",
        }
        return coordinator

    def test_prayer_time_sensors_return_datetime(
        self, mock_coordinator, mock_config_entry
    ):
        """Prayer time sensors should return datetime objects."""
        prayer_keys = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

        for sensor_desc in SENSOR_TYPES:
            if sensor_desc.key in prayer_keys:
                sensor = MuslimPrayerCompanionTimeSensor(
                    mock_coordinator, sensor_desc, mock_config_entry
                )
                value = sensor.native_value

                assert isinstance(
                    value, datetime
                ), f"Sensor '{sensor_desc.key}' should return datetime"
                assert (
                    value.tzinfo is not None
                ), f"Sensor '{sensor_desc.key}' should return timezone-aware datetime"

    def test_hijri_date_format(self, mock_coordinator, mock_config_entry):
        """Hijri date should be in DD-MM-YYYY format."""
        sensor_desc = next(s for s in SENSOR_TYPES if s.key == "hijri_date")
        sensor = MuslimPrayerCompanionTimeSensor(
            mock_coordinator, sensor_desc, mock_config_entry
        )

        value = sensor.native_value
        assert re.match(
            r"\d{2}-\d{2}-\d{4}", value
        ), f"Hijri date should match DD-MM-YYYY, got: {value}"

    def test_hijri_day_is_numeric_string(self, mock_coordinator, mock_config_entry):
        """Hijri day should be a numeric string."""
        sensor_desc = next(s for s in SENSOR_TYPES if s.key == "hijri_day")
        sensor = MuslimPrayerCompanionTimeSensor(
            mock_coordinator, sensor_desc, mock_config_entry
        )

        value = sensor.native_value
        assert value.isdigit(), f"Hijri day should be numeric, got: {value}"

    def test_countdown_format(self, mock_coordinator, mock_config_entry):
        """Countdown should be in 'Prayer in X minutes' format."""
        sensor_desc = next(s for s in SENSOR_TYPES if s.key == "next_prayer_countdown")
        sensor = MuslimPrayerCompanionTimeSensor(
            mock_coordinator, sensor_desc, mock_config_entry
        )

        value = sensor.native_value
        assert re.match(
            r"\w+ in \d+ minutes?", value
        ), f"Countdown should match 'Prayer in X minutes', got: {value}"

    def test_qibla_is_numeric(self, mock_coordinator, mock_config_entry):
        """Qibla direction should be numeric."""
        sensor_desc = next(s for s in SENSOR_TYPES if s.key == "qibla_direction")
        sensor = MuslimPrayerCompanionTimeSensor(
            mock_coordinator, sensor_desc, mock_config_entry
        )

        value = sensor.native_value
        assert isinstance(
            value, (int, float)
        ), f"Qibla direction should be numeric, got: {type(value)}"
        assert 0 <= value < 360, f"Qibla direction should be 0-360, got: {value}"

    def test_boolean_sensors_return_string(self, mock_coordinator, mock_config_entry):
        """Boolean sensors should return 'true' or 'false' strings."""
        for key in ["is_ramadan", "is_friday"]:
            sensor_desc = next(s for s in SENSOR_TYPES if s.key == key)
            sensor = MuslimPrayerCompanionTimeSensor(
                mock_coordinator, sensor_desc, mock_config_entry
            )

            value = sensor.native_value
            assert value in (
                "true",
                "false",
            ), f"Boolean sensor '{key}' should return 'true' or 'false', got: {value}"


class TestSensorAttributes:
    """Test sensor extra state attributes."""

    @pytest.fixture
    def mock_coordinator(self) -> MagicMock:
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.data = {
            "next_prayer": datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc),
            "next_prayer_name": "Asr",
            "qibla_direction": 119.5,
            "hijri_date_readable": "15-Rajab-1445",
            "is_ramadan": False,
        }
        return coordinator

    def test_next_prayer_has_prayer_attribute(
        self, mock_coordinator, mock_config_entry
    ):
        """next_prayer sensor should have 'prayer' attribute."""
        sensor_desc = next(s for s in SENSOR_TYPES if s.key == "next_prayer")
        sensor = MuslimPrayerCompanionTimeSensor(
            mock_coordinator, sensor_desc, mock_config_entry
        )

        attrs = sensor.extra_state_attributes
        assert "prayer" in attrs
        assert attrs["prayer"] == "Asr"

    def test_qibla_has_compass_direction(self, mock_coordinator, mock_config_entry):
        """qibla_direction sensor should have compass_direction attribute."""
        sensor_desc = next(s for s in SENSOR_TYPES if s.key == "qibla_direction")
        sensor = MuslimPrayerCompanionTimeSensor(
            mock_coordinator, sensor_desc, mock_config_entry
        )

        attrs = sensor.extra_state_attributes
        assert "compass_direction" in attrs
        # 119.5 degrees should be roughly ESE
        assert attrs["compass_direction"] in ["ESE", "SE", "E"]
