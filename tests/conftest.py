"""Pytest configuration and shared fixtures for Muslim Prayer Companion tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.muslim_prayer_companion import const
from custom_components.muslim_prayer_companion.api_providers.base import (
    IqamahTimesData,
    PrayerTimesData,
    ProviderConfig,
)


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config.latitude = 53.3498  # Dublin
    hass.config.longitude = -6.2603
    hass.config.time_zone = "Europe/Dublin"
    hass.config.units.temperature_unit = "°C"

    async def fake_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)

    hass.async_add_executor_job = fake_add_executor_job
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.domain = const.DOMAIN
    entry.data = {
        const.CONF_CALC_METHOD: "isna",
        const.CONF_LATITUDE: 53.3498,
        const.CONF_LONGITUDE: -6.2603,
        const.CONF_LOCATION_NAME: "Dublin",
        const.CONF_SOURCE_TYPE: const.SOURCE_CALCULATED,
        const.CONF_TIMEZONE: "Europe/Dublin",
    }
    entry.options = {
        const.CONF_IQAMAH_METHOD: const.DEFAULT_IQAMAH_METHOD,
        const.CONF_IQAMAH_OFFSETS: const.DEFAULT_IQAMAH_OFFSETS,
    }
    return entry


@pytest.fixture
def mock_ireland_config_entry() -> MagicMock:
    """Create a mock ConfigEntry for Ireland API."""
    entry = MagicMock()
    entry.entry_id = "test_ireland_entry_456"
    entry.domain = const.DOMAIN
    entry.data = {
        const.CONF_CALC_METHOD: "ie-icci",
        const.CONF_LATITUDE: 53.2663,
        const.CONF_LONGITUDE: -6.2135,
        const.CONF_LOCATION_NAME: "ICCI Dublin",
        const.CONF_SOURCE_TYPE: const.SOURCE_IRELAND,
        const.CONF_TIMEZONE: "Europe/Dublin",
    }
    entry.options = {}
    return entry


@pytest.fixture
def provider_config() -> ProviderConfig:
    """Create a basic provider configuration."""
    return ProviderConfig(
        latitude=53.3498,
        longitude=-6.2603,
        calculation_method="isna",
        timezone="Europe/Dublin",
    )


@pytest.fixture
def sample_prayer_times() -> PrayerTimesData:
    """Create sample prayer times data."""
    base_date = date.today()
    return PrayerTimesData(
        fajr=datetime(
            base_date.year, base_date.month, base_date.day, 5, 30, tzinfo=timezone.utc
        ),
        sunrise=datetime(
            base_date.year, base_date.month, base_date.day, 7, 15, tzinfo=timezone.utc
        ),
        dhuhr=datetime(
            base_date.year, base_date.month, base_date.day, 12, 30, tzinfo=timezone.utc
        ),
        asr=datetime(
            base_date.year, base_date.month, base_date.day, 15, 45, tzinfo=timezone.utc
        ),
        maghrib=datetime(
            base_date.year, base_date.month, base_date.day, 18, 30, tzinfo=timezone.utc
        ),
        isha=datetime(
            base_date.year, base_date.month, base_date.day, 20, 0, tzinfo=timezone.utc
        ),
        midnight=datetime(
            base_date.year, base_date.month, base_date.day, 23, 59, tzinfo=timezone.utc
        ),
    )


@pytest.fixture
def sample_iqamah_times() -> IqamahTimesData:
    """Create sample iqamah times data."""
    base_date = date.today()
    return IqamahTimesData(
        fajr=datetime(
            base_date.year, base_date.month, base_date.day, 5, 50, tzinfo=timezone.utc
        ),
        dhuhr=datetime(
            base_date.year, base_date.month, base_date.day, 12, 45, tzinfo=timezone.utc
        ),
        asr=datetime(
            base_date.year, base_date.month, base_date.day, 16, 0, tzinfo=timezone.utc
        ),
        maghrib=datetime(
            base_date.year, base_date.month, base_date.day, 18, 40, tzinfo=timezone.utc
        ),
        isha=datetime(
            base_date.year, base_date.month, base_date.day, 20, 15, tzinfo=timezone.utc
        ),
    )


@pytest.fixture
def icci_api_response() -> dict[str, Any]:
    """Sample ICCI API response."""
    return {
        "timetable": {
            "1": {
                "1": [[6, 45], [8, 30], [12, 30], [14, 45], [16, 30], [18, 15]],
                "2": [[6, 44], [8, 29], [12, 30], [14, 46], [16, 31], [18, 16]],
            },
            "6": {
                "15": [[3, 15], [5, 0], [13, 30], [17, 30], [21, 30], [23, 0]],
            },
        }
    }


@pytest.fixture
def wordpress_api_response() -> list[dict[str, Any]]:
    """Sample WordPress Daily Prayer Time plugin response."""
    return [
        {
            "fajr_begins": "06:45:00",
            "fajr_jamah": "07:00:00",
            "sunrise": "08:30:00",
            "zuhr_begins": "12:30:00",
            "zuhr_jamah": "13:30:00",
            "asr_mithl_1": "14:45:00",
            "asr_jamah": "15:30:00",
            "maghrib_begins": "17:00:00",
            "maghrib_jamah": "17:05:00",
            "isha_begins": "18:30:00",
            "isha_jamah": "19:30:00",
            "jumuah_time": "13:30:00",
        }
    ]


@pytest.fixture
def mock_aiohttp_session() -> MagicMock:
    """Create a mock aiohttp ClientSession."""
    session = MagicMock()
    session.get = AsyncMock()
    return session
