"""Constants for the Muslim Prayer Companion component."""

from logging import getLogger
from typing import Final

DOMAIN: Final = "muslim_prayer_companion"
NAME: Final = "Muslim Prayer Companion"
PRAYER_TIMES_ICON: Final = "mdi:calendar-clock"

# Config entry version for migrations
CONFIG_VERSION: Final = 2

# Configuration keys
CONF_CALC_METHOD: Final = "calculation_method"
CONF_SOURCE_TYPE: Final = "source_type"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_LOCATION_NAME: Final = "location_name"
CONF_USE_API: Final = "use_api"
CONF_API_KEY: Final = "api_key"
CONF_MOSQUE_ID: Final = "mosque_id"
CONF_MOSQUE_NAME: Final = "mosque_name"
CONF_IQAMAH_OFFSETS: Final = "iqamah_offsets"
CONF_IQAMAH_METHOD: Final = "iqamah_method"
CONF_ENABLE_HIJRI: Final = "enable_hijri"
CONF_ENABLE_COUNTDOWN: Final = "enable_countdown"
CONF_TIMEZONE: Final = "timezone"

# Source types
SOURCE_CALCULATED: Final = "calculated"
SOURCE_IRELAND: Final = "ireland"
SOURCE_MAWAQIT: Final = "mawaqit"
SOURCE_ALADHAN: Final = "aladhan"

# Default values
DEFAULT_CALC_METHOD: Final = "isna"
DEFAULT_SOURCE_TYPE: Final = SOURCE_CALCULATED
DEFAULT_LOCATION_NAME: Final = "Home"
DEFAULT_IQAMAH_METHOD: Final = "offset"
DEFAULT_IQAMAH_OFFSETS: Final = {
    "Fajr": 20,
    "Dhuhr": 15,
    "Asr": 15,
    "Maghrib": 10,
    "Isha": 15,
}
DEFAULT_ENABLE_HIJRI: Final = True
DEFAULT_ENABLE_COUNTDOWN: Final = True

# Standard calculation methods (using prayer-times-calculator)
STANDARD_CALC_METHODS: Final = {
    "Jafari": "jafari",
    "Karachi": "karachi",
    "Islamic Society of North America (ISNA)": "isna",
    "Muslim World League (MWL)": "mwl",
    "Makkah": "makkah",
    "Egypt": "egypt",
    "Tehran": "tehran",
    "Gulf": "gulf",
    "Kuwait": "kuwait",
    "Qatar": "qatar",
    "Singapore": "singapore",
    "France": "france",
    "Turkey": "turkey",
    "Russia": "russia",
}

# Ireland-specific calculation methods
IRELAND_CALC_METHODS: Final = {
    "Ireland - Islamic Cultural Centre of Ireland (ICCI)": "ie-icci",
    "Ireland - Muslim Community North Dublin (MCND)": "ie-mcnd",
    "Ireland - Hansfield Islamic Cultural Centre (HICC)": "ie-hicc",
    "Ireland - South Dublin Islamic Centre (SDIC)": "ie-sdic",
}

# All calculation methods (for backward compatibility)
CALC_METHODS: Final = {
    **STANDARD_CALC_METHODS,
    **IRELAND_CALC_METHODS,
}

# Prayer names
PRAYERS: Final = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
ALL_PRAYER_TIMES: Final = [
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Maghrib",
    "Isha",
    "Midnight",
]

# Event names
DATA_UPDATED: Final = "muslim_prayer_data_updated"

# Logger
LOGGER = getLogger(__package__)
