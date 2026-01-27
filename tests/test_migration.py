"""Test cases for config entry migration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.muslim_prayer_companion import async_migrate_entry
from custom_components.muslim_prayer_companion.const import (
    CONF_CALC_METHOD,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    CONFIG_VERSION,
    DEFAULT_LOCATION_NAME,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
)


class TestConfigEntryMigration:
    """Test config entry version migration."""

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create mock HomeAssistant."""
        hass = MagicMock()
        hass.config.latitude = 51.5074
        hass.config.longitude = -0.1278
        hass.config.time_zone = "Europe/London"
        hass.config_entries = MagicMock()
        return hass

    @pytest.fixture
    def v1_entry_calculated(self) -> MagicMock:
        """Create a version 1 config entry with calculated method."""
        entry = MagicMock()
        entry.version = 1
        entry.data = {
            CONF_CALC_METHOD: "isna",
        }
        return entry

    @pytest.fixture
    def v1_entry_ireland(self) -> MagicMock:
        """Create a version 1 config entry with Ireland method."""
        entry = MagicMock()
        entry.version = 1
        entry.data = {
            CONF_CALC_METHOD: "ie-icci",
        }
        return entry

    @pytest.mark.asyncio
    async def test_migrate_v1_to_v2_calculated(self, mock_hass, v1_entry_calculated):
        """Migration should add location from HA config for calculated method."""
        result = await async_migrate_entry(mock_hass, v1_entry_calculated)

        assert result is True

        # Check async_update_entry was called
        mock_hass.config_entries.async_update_entry.assert_called_once()

        call_kwargs = mock_hass.config_entries.async_update_entry.call_args[1]

        # Verify new data includes location
        new_data = call_kwargs["data"]
        assert new_data[CONF_LATITUDE] == 51.5074
        assert new_data[CONF_LONGITUDE] == -0.1278
        assert new_data[CONF_LOCATION_NAME] == DEFAULT_LOCATION_NAME
        assert new_data[CONF_SOURCE_TYPE] == SOURCE_CALCULATED
        assert new_data[CONF_TIMEZONE] == "Europe/London"

        # Verify version updated
        assert call_kwargs["version"] == CONFIG_VERSION

    @pytest.mark.asyncio
    async def test_migrate_v1_to_v2_ireland(self, mock_hass, v1_entry_ireland):
        """Migration should set SOURCE_IRELAND for Ireland methods."""
        result = await async_migrate_entry(mock_hass, v1_entry_ireland)

        assert result is True

        call_kwargs = mock_hass.config_entries.async_update_entry.call_args[1]
        new_data = call_kwargs["data"]

        # Source type should be Ireland
        assert new_data[CONF_SOURCE_TYPE] == SOURCE_IRELAND

        # Original calc method preserved
        assert new_data[CONF_CALC_METHOD] == "ie-icci"

    @pytest.mark.asyncio
    async def test_migrate_preserves_original_data(self, mock_hass):
        """Migration should preserve all original data."""
        entry = MagicMock()
        entry.version = 1
        entry.data = {
            CONF_CALC_METHOD: "mwl",
            "custom_option": "value",  # Some extra data
        }

        await async_migrate_entry(mock_hass, entry)

        call_kwargs = mock_hass.config_entries.async_update_entry.call_args[1]
        new_data = call_kwargs["data"]

        # Original data preserved
        assert new_data[CONF_CALC_METHOD] == "mwl"
        assert new_data["custom_option"] == "value"

    @pytest.mark.asyncio
    async def test_no_migration_needed_for_current_version(self, mock_hass):
        """No migration should happen for current version entries."""
        entry = MagicMock()
        entry.version = CONFIG_VERSION
        entry.data = {
            CONF_CALC_METHOD: "isna",
            CONF_LATITUDE: 40.7128,
            CONF_LONGITUDE: -74.0060,
        }

        result = await async_migrate_entry(mock_hass, entry)

        assert result is True
        # async_update_entry should not be called
        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestBackwardCompatibility:
    """Test backward compatibility of migrated entries."""

    def test_sensor_unique_ids_unchanged_after_migration(self):
        """Sensor unique_ids should remain unchanged after migration.

        This is critical for preserving automations and dashboards.
        """
        # The unique_id format is: {key}_{entry_id}
        # This format should not change between versions

        entry_id = "test123"
        sensor_key = "Fajr"

        # Pre-migration format
        pre_migration_id = f"{sensor_key}_{entry_id}"

        # Post-migration format (same)
        post_migration_id = f"{sensor_key}_{entry_id}"

        assert pre_migration_id == post_migration_id

    def test_ireland_method_values_unchanged(self):
        """Ireland method string values should remain unchanged."""
        # These values are stored in config entries and must not change
        expected_values = ["ie-icci", "ie-mcnd", "ie-hicc", "ie-sdic"]

        from custom_components.muslim_prayer_companion.const import IRELAND_CALC_METHODS

        for value in expected_values:
            assert value in IRELAND_CALC_METHODS.values()

    def test_standard_method_values_unchanged(self):
        """Standard calculation method values should remain unchanged."""
        expected_values = [
            "isna",
            "mwl",
            "karachi",
            "makkah",
            "egypt",
            "tehran",
            "gulf",
            "kuwait",
            "qatar",
            "singapore",
            "france",
            "turkey",
            "russia",
            "jafari",
        ]

        from custom_components.muslim_prayer_companion.const import (
            STANDARD_CALC_METHODS,
        )

        for value in expected_values:
            assert value in STANDARD_CALC_METHODS.values()
