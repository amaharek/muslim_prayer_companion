"""
Test cases for the Muslim Prayer Companion integration.
These tests cover coordinator updates, sensor state conversion, and the config flow.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util.dt import as_utc
from test_helpers import (
    create_fake_config_entry,
    create_fake_hass,
    dummy_coordinator_data,
    dummy_hijri_date,
    dummy_prayer_times_datetime,
)

from custom_components.muslim_prayer_companion import config_flow, const, sensor
from custom_components.muslim_prayer_companion.api_providers.base import (
    PrayerTimesData,
    ProviderConfig,
)
from custom_components.muslim_prayer_companion.coordinator import (
    MuslimPrayerCompanionDataUpdateCoordinator,
)


@pytest.fixture
def fake_hass():
    """Return a fake HomeAssistant instance."""
    return create_fake_hass()


@pytest.fixture
def fake_config_entry():
    """Return a fake ConfigEntry with default options."""
    return create_fake_config_entry()


@pytest.fixture
def coordinator_instance(fake_hass, fake_config_entry):
    """Instantiate the coordinator with fake hass and config entry."""
    coord = MuslimPrayerCompanionDataUpdateCoordinator(
        fake_hass,
        fake_config_entry,
    )
    return coord


class TestCoordinator:
    """Test coordinator functionality."""

    def test_coordinator_initialization(
        self, coordinator_instance, fake_hass, fake_config_entry
    ):
        """Test coordinator initializes with correct values."""
        assert (
            coordinator_instance.latitude == fake_config_entry.data[const.CONF_LATITUDE]
        )
        assert (
            coordinator_instance.longitude
            == fake_config_entry.data[const.CONF_LONGITUDE]
        )
        assert (
            coordinator_instance.location_name
            == fake_config_entry.data[const.CONF_LOCATION_NAME]
        )

    def test_coordinator_calc_method(self, coordinator_instance, fake_config_entry):
        """Test coordinator returns correct calculation method."""
        assert (
            coordinator_instance.calc_method
            == fake_config_entry.data[const.CONF_CALC_METHOD]
        )

    def test_coordinator_iqamah_method(self, coordinator_instance, fake_config_entry):
        """Test coordinator returns correct iqamah method."""
        assert coordinator_instance.iqamah_method == const.DEFAULT_IQAMAH_METHOD


class TestSensorEntity:
    """Test sensor entity creation and values."""

    def test_sensor_unique_id_format(self, fake_config_entry):
        """Test sensor unique_id follows backward compatible format."""
        coordinator = MagicMock()
        coordinator.data = dummy_coordinator_data()
        coordinator.config_entry = fake_config_entry

        sensor_desc = sensor.SENSOR_TYPES[0]  # Fajr
        sensor_entity = sensor.MuslimPrayerCompanionTimeSensor(
            coordinator, sensor_desc, fake_config_entry
        )

        # Format should be {key}_{entry_id}
        expected_id = f"{sensor_desc.key}_{fake_config_entry.entry_id}"
        assert sensor_entity.unique_id == expected_id

    def test_sensor_native_value_datetime(self, fake_config_entry):
        """Test sensor returns datetime for timestamp sensors."""
        coordinator = MagicMock()
        coordinator.data = dummy_coordinator_data()

        sensor_desc = sensor.SENSOR_TYPES[0]  # Fajr
        sensor_entity = sensor.MuslimPrayerCompanionTimeSensor(
            coordinator, sensor_desc, fake_config_entry
        )

        value = sensor_entity.native_value
        assert isinstance(value, datetime)

    def test_sensor_native_value_string(self, fake_config_entry):
        """Test sensor returns string for non-timestamp sensors."""
        coordinator = MagicMock()
        coordinator.data = dummy_coordinator_data()

        # Find hijri_date sensor (string type)
        sensor_desc = next(s for s in sensor.SENSOR_TYPES if s.key == "hijri_date")
        sensor_entity = sensor.MuslimPrayerCompanionTimeSensor(
            coordinator, sensor_desc, fake_config_entry
        )

        value = sensor_entity.native_value
        assert isinstance(value, str)

    def test_next_prayer_has_prayer_attribute(self, fake_config_entry):
        """Test next_prayer sensor has prayer name in attributes."""
        coordinator = MagicMock()
        coordinator.data = dummy_coordinator_data()

        sensor_desc = next(s for s in sensor.SENSOR_TYPES if s.key == "next_prayer")
        sensor_entity = sensor.MuslimPrayerCompanionTimeSensor(
            coordinator, sensor_desc, fake_config_entry
        )

        attrs = sensor_entity.extra_state_attributes
        assert "prayer" in attrs
        assert attrs["prayer"] == "Asr"


class TestConfigFlow:
    """Test config flow steps."""

    @pytest.mark.asyncio
    async def test_config_flow_user_step(self, fake_hass):
        """Test the user step shows source selection."""
        flow = config_flow.MuslimPrayerCompanionConfigFlow()
        flow.hass = fake_hass

        result = await flow.async_step_user(None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_config_flow_user_to_location(self, fake_hass):
        """Test selecting calculated source goes to location step."""
        flow = config_flow.MuslimPrayerCompanionConfigFlow()
        flow.hass = fake_hass

        result = await flow.async_step_user({"source_type": "calculated"})

        assert result["type"] == "form"
        assert result["step_id"] == "location"

    @pytest.mark.asyncio
    async def test_config_flow_user_to_ireland(self, fake_hass):
        """Test selecting Ireland source goes to Ireland step."""
        flow = config_flow.MuslimPrayerCompanionConfigFlow()
        flow.hass = fake_hass

        result = await flow.async_step_user({"source_type": "ireland"})

        assert result["type"] == "form"
        assert result["step_id"] == "ireland"

    @pytest.mark.asyncio
    async def test_config_flow_ireland_creates_entry(self, fake_hass):
        """Test Ireland step creates config entry."""
        flow = config_flow.MuslimPrayerCompanionConfigFlow()
        flow.hass = fake_hass
        flow._data = {const.CONF_SOURCE_TYPE: const.SOURCE_IRELAND}

        result = await flow.async_step_ireland(
            {
                const.CONF_CALC_METHOD: "ie-icci",
                const.CONF_LOCATION_NAME: "ICCI Dublin",
            }
        )

        assert result["type"] == "create_entry"
        assert const.CONF_CALC_METHOD in result["data"]
        assert result["data"][const.CONF_CALC_METHOD] == "ie-icci"

    @pytest.mark.asyncio
    async def test_config_flow_method_creates_entry(self, fake_hass):
        """Test method step creates config entry."""
        flow = config_flow.MuslimPrayerCompanionConfigFlow()
        flow.hass = fake_hass
        flow._data = {
            const.CONF_SOURCE_TYPE: const.SOURCE_CALCULATED,
            const.CONF_LATITUDE: 51.5,
            const.CONF_LONGITUDE: -0.1,
            const.CONF_LOCATION_NAME: "London",
            const.CONF_TIMEZONE: "Europe/London",
        }

        result = await flow.async_step_method(
            {
                const.CONF_CALC_METHOD: "isna",
            }
        )

        assert result["type"] == "create_entry"
        assert result["data"][const.CONF_CALC_METHOD] == "isna"


class TestOptionsFlow:
    """Test options flow."""

    @pytest.mark.asyncio
    async def test_options_flow_init(self, fake_config_entry):
        """Test options flow shows current values."""
        flow = config_flow.MuslimPrayerCompanionOptionsFlow(fake_config_entry)

        result = await flow.async_step_init(None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_flow_creates_entry(self, fake_config_entry):
        """Test options flow creates entry on submit."""
        flow = config_flow.MuslimPrayerCompanionOptionsFlow(fake_config_entry)

        result = await flow.async_step_init(
            {
                const.CONF_CALC_METHOD: "mwl",
                const.CONF_IQAMAH_METHOD: "offset",
                const.CONF_ENABLE_HIJRI: True,
                const.CONF_ENABLE_COUNTDOWN: True,
            }
        )

        assert result["type"] == "create_entry"
        assert result["data"][const.CONF_CALC_METHOD] == "mwl"


class TestMultiInstance:
    """Test multi-instance support."""

    def test_multiple_coordinators_have_unique_names(self, fake_hass):
        """Test multiple coordinators have unique names."""
        entry1 = create_fake_config_entry(entry_id="entry1")
        entry2 = create_fake_config_entry(entry_id="entry2")

        coord1 = MuslimPrayerCompanionDataUpdateCoordinator(fake_hass, entry1)
        coord2 = MuslimPrayerCompanionDataUpdateCoordinator(fake_hass, entry2)

        assert coord1.name != coord2.name
        assert "entry1" in coord1.name
        assert "entry2" in coord2.name

    def test_sensors_have_unique_ids_per_entry(self, fake_config_entry):
        """Test sensors from different entries have unique IDs."""
        entry1 = create_fake_config_entry(entry_id="entry1")
        entry2 = create_fake_config_entry(entry_id="entry2")

        coordinator = MagicMock()
        coordinator.data = dummy_coordinator_data()

        sensor_desc = sensor.SENSOR_TYPES[0]

        sensor1 = sensor.MuslimPrayerCompanionTimeSensor(
            coordinator, sensor_desc, entry1
        )
        sensor2 = sensor.MuslimPrayerCompanionTimeSensor(
            coordinator, sensor_desc, entry2
        )

        assert sensor1.unique_id != sensor2.unique_id
        assert "entry1" in sensor1.unique_id
        assert "entry2" in sensor2.unique_id
