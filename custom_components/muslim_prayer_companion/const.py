"""Constants for the Muslim Prayer Companion component."""

from __future__ import annotations

from logging import getLogger
from typing import Final

DOMAIN: Final = "muslim_prayer_companion"
NAME: Final = "Muslim Prayer Companion"

# Config entry version. 1 = 3.0.x, 2 = unreleased refactoring-v2, 3 = 4.0.0.
CONFIG_VERSION: Final = 3

# --- Config entry data (identity, changed only by the reconfigure flow) ---
CONF_SOURCE_TYPE: Final = "source_type"
CONF_CALC_METHOD: Final = "calculation_method"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_LOCATION_NAME: Final = "location_name"
CONF_TIMEZONE: Final = "timezone"
# Form-only field names
CONF_MOSQUE: Final = "mosque"
CONF_LOCATION: Final = "location"

# --- Config entry options (everything the user can change later) ---
CONF_IQAMAH_METHOD: Final = "iqamah_method"
CONF_IQAMAH_OFFSETS: Final = "iqamah_offsets"
CONF_IQAMAH_API_URL: Final = "iqamah_api_url"
CONF_FRIDAY_MOSQUES: Final = "friday_mosques"
CONF_HIJRI_ADJUSTMENT: Final = "hijri_adjustment"
CONF_HIJRI_CHANGE_AT_MAGHRIB: Final = "hijri_change_at_maghrib"
CONF_IMSAK_MINUTES: Final = "imsak_minutes"
CONF_ENABLED_GROUPS: Final = "enabled_groups"
CONF_COUNTDOWN_FORMAT: Final = "countdown_format"
CONF_PRAYER_WINDOW_MINUTES: Final = "prayer_window_minutes"

# Friday mosque item keys (inside CONF_FRIDAY_MOSQUES)
CONF_FRIDAY_SLUG: Final = "slug"
CONF_FRIDAY_NAME: Final = "name"
CONF_FRIDAY_SOURCE: Final = "source"
CONF_FRIDAY_JUMUAH_1: Final = "jumuah_1"
CONF_FRIDAY_JUMUAH_2: Final = "jumuah_2"
CONF_FRIDAY_LABEL_1: Final = "label_1"
CONF_FRIDAY_LABEL_2: Final = "label_2"
FRIDAY_SOURCE_MANUAL: Final = "manual"
MAX_FRIDAY_MOSQUES: Final = 10
MAX_FRIDAY_LABEL_LENGTH: Final = 40

# --- Source types ---
SOURCE_CALCULATED: Final = "calculated"
SOURCE_IRELAND: Final = "ireland"
# Reserved for a future provider; not offered in the UI yet.
SOURCE_MAWAQIT: Final = "mawaqit"
SOURCE_TYPES: Final = (SOURCE_CALCULATED, SOURCE_IRELAND)

# --- Defaults ---
DEFAULT_SOURCE_TYPE: Final = SOURCE_CALCULATED
DEFAULT_CALC_METHOD: Final = "isna"
DEFAULT_FALLBACK_CALC_METHOD: Final = "isna"
DEFAULT_LOCATION_NAME: Final = "Home"

# --- Iqamah ---
IQAMAH_METHOD_OFFSET: Final = "offset"
IQAMAH_METHOD_MOSQUE: Final = "mosque"
IQAMAH_METHOD_API: Final = "api"
IQAMAH_METHOD_DISABLED: Final = "disabled"
IQAMAH_METHODS: Final = (
    IQAMAH_METHOD_OFFSET,
    IQAMAH_METHOD_MOSQUE,
    IQAMAH_METHOD_API,
    IQAMAH_METHOD_DISABLED,
)
DEFAULT_IQAMAH_METHOD: Final = IQAMAH_METHOD_OFFSET
DEFAULT_IQAMAH_OFFSETS: Final[dict[str, int]] = {
    "Fajr": 20,
    "Dhuhr": 15,
    "Asr": 15,
    "Maghrib": 10,
    "Isha": 15,
}
MAX_IQAMAH_OFFSET_MINUTES: Final = 120

# --- Hijri ---
DEFAULT_HIJRI_ADJUSTMENT: Final = 0
MIN_HIJRI_ADJUSTMENT: Final = -2
MAX_HIJRI_ADJUSTMENT: Final = 2
DEFAULT_HIJRI_CHANGE_AT_MAGHRIB: Final = False
DEFAULT_IMSAK_MINUTES: Final = 10
MAX_IMSAK_MINUTES: Final = 60

# --- Sensor groups and display ---
GROUP_PRAYER_TIMES: Final = "prayer_times"  # always on
GROUP_IQAMAH: Final = "iqamah"
GROUP_HIJRI: Final = "hijri"
GROUP_COUNTDOWN: Final = "countdown"
GROUP_QIBLA: Final = "qibla"
GROUP_SPECIAL_DATES: Final = "special_dates"
GROUP_FRIDAY: Final = "friday"
SENSOR_GROUPS: Final = (
    GROUP_IQAMAH,
    GROUP_HIJRI,
    GROUP_COUNTDOWN,
    GROUP_QIBLA,
    GROUP_SPECIAL_DATES,
    GROUP_FRIDAY,
)

COUNTDOWN_FORMAT_SENTENCE: Final = "sentence"  # "Asr in 45 minutes"
COUNTDOWN_FORMAT_CLOCK: Final = "clock"  # "00:45"
COUNTDOWN_FORMAT_SHORT: Final = "short"  # "45"
COUNTDOWN_FORMATS: Final = (
    COUNTDOWN_FORMAT_SENTENCE,
    COUNTDOWN_FORMAT_CLOCK,
    COUNTDOWN_FORMAT_SHORT,
)
DEFAULT_COUNTDOWN_FORMAT: Final = COUNTDOWN_FORMAT_SENTENCE
DEFAULT_PRAYER_WINDOW_MINUTES: Final = 30
MAX_PRAYER_WINDOW_MINUTES: Final = 180

# --- Calculation methods (prayer-times-calculator-offline) ---
STANDARD_CALC_METHODS: Final[list[str]] = [
    "jafari",
    "karachi",
    "isna",
    "mwl",
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
    "moonsighting",
    "dubai",
    "jakim",
    "tunisia",
    "algeria",
    "kemenag",
    "morocco",
    "portugal",
    "jordan",
]

# --- Prayer names ---
PRAYERS: Final[list[str]] = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
ALL_PRAYER_TIMES: Final[list[str]] = [
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Maghrib",
    "Isha",
    "Midnight",
]

# --- Runtime ---
ATTR_SOURCE: Final = "source"
ISSUE_PROVIDER_FALLBACK: Final = "provider_fallback"
EVENT_PRAYER_TIME: Final = "muslim_prayer_companion_event"
SERVICE_GET_PRAYER_TIMES: Final = "get_prayer_times"
PROVIDER_TIMEOUT_SECONDS: Final = 15
PAYLOAD_CACHE_SECONDS: Final = 600
RETRY_DELAYS: Final = (60, 120, 300, 600)
UPDATE_INTERVAL_MINUTES: Final = 60

TIME_HHMM_RE: Final = r"^([01]\d|2[0-3]):[0-5]\d$"

LOGGER = getLogger(__package__)
