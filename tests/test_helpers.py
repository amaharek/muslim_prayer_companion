"""Test helpers for Muslim Prayer Companion integration."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

from custom_components.muslim_prayer_companion import const


def create_fake_hass():
    """Return a fake HomeAssistant instance with minimal configuration."""
    hass = MagicMock()
    hass.config.latitude = 51.5074  # London
    hass.config.longitude = -0.1278
    hass.config.time_zone = "Europe/London"

    async def fake_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)

    hass.async_add_executor_job = fake_add_executor_job
    return hass


def create_fake_config_entry(
    domain="muslim_prayer_companion", data=None, options=None, entry_id="test123"
):
    """Return a fake ConfigEntry with given data and options."""
    if data is None:
        data = {
            const.CONF_CALC_METHOD: const.DEFAULT_CALC_METHOD,
            const.CONF_LATITUDE: 51.5074,
            const.CONF_LONGITUDE: -0.1278,
            const.CONF_LOCATION_NAME: const.DEFAULT_LOCATION_NAME,
            const.CONF_SOURCE_TYPE: const.SOURCE_CALCULATED,
            const.CONF_TIMEZONE: "Europe/London",
        }
    if options is None:
        options = {
            const.CONF_IQAMAH_METHOD: const.DEFAULT_IQAMAH_METHOD,
            const.CONF_IQAMAH_OFFSETS: const.DEFAULT_IQAMAH_OFFSETS,
        }

    entry = MagicMock()
    entry.domain = domain
    entry.data = data
    entry.options = options
    entry.entry_id = entry_id
    return entry


def dummy_prayer_times():
    """Return dummy prayer times as expected from providers.

    Returns dict with HH:MM format strings (legacy format).
    """
    return {
        "Fajr": "05:00",
        "Sunrise": "06:30",
        "Dhuhr": "12:00",
        "Asr": "15:30",
        "Maghrib": "18:00",
        "Isha": "19:30",
        "Midnight": "00:00",
    }


def dummy_prayer_times_datetime():
    """Return dummy prayer times as UTC datetime objects."""
    today = date.today()
    return {
        "Fajr": datetime(today.year, today.month, today.day, 5, 0, tzinfo=timezone.utc),
        "Sunrise": datetime(
            today.year, today.month, today.day, 6, 30, tzinfo=timezone.utc
        ),
        "Dhuhr": datetime(
            today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc
        ),
        "Asr": datetime(
            today.year, today.month, today.day, 15, 30, tzinfo=timezone.utc
        ),
        "Maghrib": datetime(
            today.year, today.month, today.day, 18, 0, tzinfo=timezone.utc
        ),
        "Isha": datetime(
            today.year, today.month, today.day, 19, 30, tzinfo=timezone.utc
        ),
        "Midnight": datetime(
            today.year, today.month, today.day, 23, 59, tzinfo=timezone.utc
        ),
    }


def dummy_hijri_date():
    """Return dummy Hijri date information."""
    return {
        "hijri_date": "10-09-1444",
        "hijri_day": "10",
        "hijri_month_num": 9,
        "hijri_month_readable": "Ramadan",
        "hijri_year": "1444",
        "hijri_date_readable": "10-Ramadan-1444",
        "hijri_day_month_readable": "10-Ramadan",
    }


def dummy_coordinator_data():
    """Return complete coordinator data for testing."""
    today = date.today()
    now = datetime.now(timezone.utc)

    # Find next prayer (simple logic for testing)
    next_prayer_time = datetime(
        today.year, today.month, today.day, 15, 30, tzinfo=timezone.utc
    )
    if next_prayer_time < now:
        next_prayer_time = next_prayer_time + timedelta(days=1)

    data = {
        # Prayer times
        **dummy_prayer_times_datetime(),
        # Iqamah times
        "iqamah_Fajr": datetime(
            today.year, today.month, today.day, 5, 20, tzinfo=timezone.utc
        ),
        "iqamah_Dhuhr": datetime(
            today.year, today.month, today.day, 12, 15, tzinfo=timezone.utc
        ),
        "iqamah_Asr": datetime(
            today.year, today.month, today.day, 15, 45, tzinfo=timezone.utc
        ),
        "iqamah_Maghrib": datetime(
            today.year, today.month, today.day, 18, 10, tzinfo=timezone.utc
        ),
        "iqamah_Isha": datetime(
            today.year, today.month, today.day, 19, 45, tzinfo=timezone.utc
        ),
        # Hijri date
        **dummy_hijri_date(),
        # Next prayer
        "next_prayer": next_prayer_time,
        "next_prayer_name": "Asr",
        "next_prayer_minutes": 45,
        "next_prayer_countdown": "Asr in 45 minutes",
        # Additional data
        "current_prayer_period": "Between Dhuhr and Asr",
        "qibla_direction": 119.5,
        "location_name": "Home",
        "is_ramadan": False,
        "is_friday": today.weekday() == 4,
        "special_night": "",
    }

    return data
