# Muslim Prayer Companion

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![Downloads][downloads-shield]][downloads]

Muslim Prayer Companion is a Home Assistant Community Store (HACS) integration that provides accurate prayer times, Iqamah times, Hijri calendar information, and Islamic companion features. Supports **multiple locations/mosques** simultaneously with a clean provider-based architecture.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Sensors Reference](#sensors-reference)
- [Sensor Output Formats](#sensor-output-formats)
- [Automation Examples](#automation-examples)
- [Architecture](#architecture)
- [Creating Custom API Providers](#creating-custom-api-providers)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Features

### Core Features

- **Accurate Prayer Times** - Calculate prayer times for any location worldwide
- **Multiple Calculation Methods** - ISNA, MWL, Makkah, Egypt, and 10+ more
- **Iqamah Times** - Configurable offset-based or API-fetched congregation times
- **Hijri Calendar** - Full Islamic date information with month names
- **Next Prayer Tracking** - Always know which prayer is coming up

### New in v3.0.0

- **Multi-Instance Support** - Add multiple locations/mosques simultaneously
- **Countdown Sensors** - "Asr in 45 minutes" and minutes until next prayer
- **Qibla Direction** - Compass bearing to Mecca from your location
- **Jumu'a (Friday) Prayer** - Dedicated Friday prayer time sensor
- **Special Night Detection** - Laylatul Qadr, Laylatul Bara'ah, etc.
- **Ramadan Detection** - Automatic detection of Ramadan month
- **Ireland Mosque APIs** - Direct integration with ICCI, MCND, HICC, SDIC

### Platforms

| Platform | Description                                                             |
| -------- | ----------------------------------------------------------------------- |
| `sensor` | 30+ sensors for prayer times, Iqamah, Hijri dates, and Islamic features |

---

## Installation

### Prerequisites

- [Home Assistant](https://www.home-assistant.io/) 2024.1.0 or newer
- [HACS](https://hacs.xyz/) installed

### Installation Steps

1. **Open HACS** in your Home Assistant instance

2. **Add Custom Repository:**
   - Click the three dots (⋮) → **Custom repositories**
   - Add URL: `https://github.com/amaharek/muslim_prayer_companion`
   - Category: **Integration**
   - Click **Add**

3. **Install the Integration:**
   - Search for "Muslim Prayer Companion" in HACS
   - Click **Download**

4. **Restart Home Assistant**

5. **Add the Integration:**
   - Go to **Settings → Devices & Services → Add Integration**
   - Search for "Muslim Prayer Companion"
   - Follow the setup wizard

---

## Configuration

### Multi-Step Setup Wizard

The integration uses a 3-step configuration flow:

#### Step 1: Choose Source Type

| Option                         | Description                                         |
| ------------------------------ | --------------------------------------------------- |
| **Calculate from coordinates** | Use mathematical calculation based on your location |
| **Ireland Mosque API**         | Fetch times directly from Irish mosque websites     |

#### Step 2: Location Configuration

| Option                          | Description                                              |
| ------------------------------- | -------------------------------------------------------- |
| **Use Home Assistant location** | Use coordinates from your HA settings                    |
| **Custom coordinates**          | Enter specific latitude/longitude                        |
| **Location name**               | Friendly name for this location (e.g., "Home", "Office") |

#### Step 3: Calculation Method

Select your preferred calculation method (see table below).

### Calculation Methods

#### Standard Methods (Worldwide)

| Method      | Organization                            | Fajr Angle | Isha Angle           |
| ----------- | --------------------------------------- | ---------- | -------------------- |
| `isna`      | Islamic Society of North America        | 15°        | 15°                  |
| `mwl`       | Muslim World League                     | 18°        | 17°                  |
| `makkah`    | Umm al-Qura University, Makkah          | 18.5°      | 90 min after Maghrib |
| `egypt`     | Egyptian General Authority of Survey    | 19.5°      | 17.5°                |
| `karachi`   | University of Islamic Sciences, Karachi | 18°        | 18°                  |
| `tehran`    | Institute of Geophysics, Tehran         | 17.7°      | 14°                  |
| `jafari`    | Shia Ithna-Ashari                       | 16°        | 14°                  |
| `gulf`      | Gulf Region                             | 19.5°      | 90 min after Maghrib |
| `kuwait`    | Kuwait                                  | 18°        | 17.5°                |
| `qatar`     | Qatar                                   | 18°        | 90 min after Maghrib |
| `singapore` | Singapore                               | 20°        | 18°                  |
| `france`    | France                                  | 12°        | 12°                  |
| `turkey`    | Turkey                                  | 18°        | 17°                  |
| `russia`    | Russia                                  | 16°        | 15°                  |

#### Ireland Mosque APIs

| Method    | Mosque                             | Features              |
| --------- | ---------------------------------- | --------------------- |
| `ie-icci` | Islamic Cultural Centre of Ireland | Prayer times          |
| `ie-mcnd` | Muslim Community North Dublin      | Prayer + Iqamah times |
| `ie-hicc` | Hansfield Islamic Cultural Centre  | Prayer + Iqamah times |
| `ie-sdic` | South Dublin Islamic Centre        | Prayer + Iqamah times |

### Options (After Setup)

Go to **Settings → Devices & Services → Muslim Prayer Companion → Configure**:

| Option                       | Description                                         |
| ---------------------------- | --------------------------------------------------- |
| **Calculation method**       | Change the prayer calculation method                |
| **Iqamah method**            | `offset` (add minutes to prayer time) or `disabled` |
| **Enable Hijri sensors**     | Show/hide Hijri date sensors                        |
| **Enable countdown sensors** | Show/hide countdown sensors                         |

---

## Sensors Reference

### Prayer Time Sensors

| Sensor         | Entity ID                                         | Device Class | Description           |
| -------------- | ------------------------------------------------- | ------------ | --------------------- |
| Fajr Prayer    | `sensor.muslim_prayer_companion_*_fajr_prayer`    | `timestamp`  | Dawn prayer time      |
| Sunrise        | `sensor.muslim_prayer_companion_*_sunrise_time`   | `timestamp`  | Sunrise time          |
| Dhuhr Prayer   | `sensor.muslim_prayer_companion_*_dhuhr_prayer`   | `timestamp`  | Noon prayer time      |
| Asr Prayer     | `sensor.muslim_prayer_companion_*_asr_prayer`     | `timestamp`  | Afternoon prayer time |
| Maghrib Prayer | `sensor.muslim_prayer_companion_*_maghrib_prayer` | `timestamp`  | Sunset prayer time    |
| Isha Prayer    | `sensor.muslim_prayer_companion_*_isha_prayer`    | `timestamp`  | Night prayer time     |
| Midnight       | `sensor.muslim_prayer_companion_*_midnight_time`  | `timestamp`  | Islamic midnight      |

### Iqamah Time Sensors

| Sensor         | Entity ID                                         | Device Class | Description               |
| -------------- | ------------------------------------------------- | ------------ | ------------------------- |
| Iqamah Fajr    | `sensor.muslim_prayer_companion_*_iqamah_fajr`    | `timestamp`  | Fajr congregation time    |
| Iqamah Dhuhr   | `sensor.muslim_prayer_companion_*_iqamah_dhuhr`   | `timestamp`  | Dhuhr congregation time   |
| Iqamah Asr     | `sensor.muslim_prayer_companion_*_iqamah_asr`     | `timestamp`  | Asr congregation time     |
| Iqamah Maghrib | `sensor.muslim_prayer_companion_*_iqamah_maghrib` | `timestamp`  | Maghrib congregation time |
| Iqamah Isha    | `sensor.muslim_prayer_companion_*_iqamah_isha`    | `timestamp`  | Isha congregation time    |

### Hijri Date Sensors

| Sensor              | Entity ID                                              | Description                |
| ------------------- | ------------------------------------------------------ | -------------------------- |
| Hijri Date          | `sensor.muslim_prayer_companion_*_hijri_date`          | Date in DD-MM-YYYY format  |
| Hijri Day           | `sensor.muslim_prayer_companion_*_hijri_day`           | Day number (1-30)          |
| Hijri Month Number  | `sensor.muslim_prayer_companion_*_hijri_month_number`  | Month number (1-12)        |
| Hijri Month         | `sensor.muslim_prayer_companion_*_hijri_month`         | Month name (Ramadan, etc.) |
| Hijri Year          | `sensor.muslim_prayer_companion_*_hijri_year`          | Year (1446, etc.)          |
| Hijri Date Readable | `sensor.muslim_prayer_companion_*_hijri_date_readable` | "15-Ramadan-1446"          |
| Hijri Day and Month | `sensor.muslim_prayer_companion_*_hijri_day_and_month` | "15-Ramadan"               |

### Next Prayer Sensors

| Sensor                | Entity ID                                                | Device Class | Description               |
| --------------------- | -------------------------------------------------------- | ------------ | ------------------------- |
| Next Prayer           | `sensor.muslim_prayer_companion_*_next_prayer`           | `timestamp`  | Time of next prayer       |
| Next Prayer Countdown | `sensor.muslim_prayer_companion_*_next_prayer_countdown` | -            | "Asr in 45 minutes"       |
| Next Prayer Minutes   | `sensor.muslim_prayer_companion_*_next_prayer_minutes`   | -            | Minutes until next prayer |

### Additional Sensors

| Sensor                | Entity ID                                                | Type        | Description                     |
| --------------------- | -------------------------------------------------------- | ----------- | ------------------------------- |
| Jumu'a Time           | `sensor.muslim_prayer_companion_*_jumu_a_time`           | `timestamp` | Friday prayer (only on Fridays) |
| Current Prayer Period | `sensor.muslim_prayer_companion_*_current_prayer_period` | `string`    | "Between Dhuhr and Asr"         |
| Qibla Direction       | `sensor.muslim_prayer_companion_*_qibla_direction`       | `number`    | Degrees from North (0-360°)     |
| Location              | `sensor.muslim_prayer_companion_*_location`              | `string`    | Location name                   |
| Is Ramadan            | `sensor.muslim_prayer_companion_*_is_ramadan`            | `boolean`   | "true" during Ramadan           |
| Is Friday             | `sensor.muslim_prayer_companion_*_is_friday`             | `boolean`   | "true" on Fridays               |
| Special Night         | `sensor.muslim_prayer_companion_*_special_night`         | `string`    | Laylatul Qadr, etc.             |

---

## Sensor Output Formats

### Timestamp Sensors (Prayer Times, Iqamah Times)

**Format:** ISO 8601 UTC datetime string

```
2024-02-10T05:30:00+00:00
```

**Device Class:** `timestamp`

**Home Assistant Display:** Automatically converted to your local timezone

**Example States:**

```yaml
sensor.muslim_prayer_companion_home_fajr_prayer:
  state: "2024-02-10T05:30:00+00:00"
  attributes:
    device_class: timestamp
    friendly_name: "Fajr Prayer"
    icon: mdi:weather-sunset-up
```

### Next Prayer Sensor

**Format:** ISO 8601 UTC datetime + attributes

```yaml
sensor.muslim_prayer_companion_home_next_prayer:
  state: "2024-02-10T15:30:00+00:00"
  attributes:
    prayer: "Asr" # Name of the next prayer
    device_class: timestamp
    friendly_name: "Next Prayer"
```

### Countdown Sensors

**Next Prayer Countdown:**

```yaml
sensor.muslim_prayer_companion_home_next_prayer_countdown:
  state: "Asr in 45 minutes"
  attributes:
    friendly_name: "Next Prayer Countdown"
    icon: mdi:timer-outline
```

**Next Prayer Minutes:**

```yaml
sensor.muslim_prayer_companion_home_next_prayer_minutes:
  state: 45
  attributes:
    unit_of_measurement: "min"
    state_class: measurement
    friendly_name: "Next Prayer Minutes"
```

### Hijri Date Sensors

**Hijri Date (DD-MM-YYYY):**

```yaml
sensor.muslim_prayer_companion_home_hijri_date:
  state: "15-09-1446"
  attributes:
    friendly_name: "Hijri Date"
    icon: mdi:calendar-islamic
```

**Hijri Month:**

```yaml
sensor.muslim_prayer_companion_home_hijri_month:
  state: "Ramadan"
  attributes:
    friendly_name: "Hijri Month"
```

**Hijri Date Readable:**

```yaml
sensor.muslim_prayer_companion_home_hijri_date_readable:
  state: "15-Ramadan-1446"
  attributes:
    is_ramadan: true
    friendly_name: "Hijri Date Readable"
```

### Qibla Direction Sensor

**Format:** Degrees from North (0-360)

```yaml
sensor.muslim_prayer_companion_home_qibla_direction:
  state: 119.5
  attributes:
    compass_direction: "ESE" # Compass direction name
    unit_of_measurement: "°"
    state_class: measurement
    friendly_name: "Qibla Direction"
```

### Boolean Sensors

**Format:** String "true" or "false"

```yaml
sensor.muslim_prayer_companion_home_is_ramadan:
  state: "true"
  attributes:
    friendly_name: "Is Ramadan"
    icon: mdi:moon-waning-crescent

sensor.muslim_prayer_companion_home_is_friday:
  state: "false"
  attributes:
    friendly_name: "Is Friday"
```

### Special Night Sensor

**Format:** String (empty when no special night)

```yaml
# During Laylatul Qadr
sensor.muslim_prayer_companion_home_special_night:
  state: "Possible Laylatul Qadr (Night 27)"

# Normal nights
sensor.muslim_prayer_companion_home_special_night:
  state: ""
```

**Possible values:**

- `"Possible Laylatul Qadr (Night 21/23/25/27/29)"` - Last 10 nights of Ramadan
- `"Night before Eid al-Fitr"` - 29th Ramadan
- `"Night of Arafah"` - 9th Dhul Hijjah
- `"Laylatul Bara'ah (Night of Forgiveness)"` - 15th Sha'ban
- `"Laylatul Mi'raj (Night Journey)"` - 27th Rajab
- `"Night before Ashura"` - 9th Muharram
- `""` - No special night

### Current Prayer Period Sensor

**Format:** Descriptive string

```yaml
sensor.muslim_prayer_companion_home_current_prayer_period:
  state: "Between Dhuhr and Asr"
```

**Possible values:**

- `"Before Fajr"`
- `"Between Fajr and Sunrise"`
- `"Between Sunrise and Dhuhr"`
- `"Between Dhuhr and Asr"`
- `"Between Asr and Maghrib"`
- `"Between Maghrib and Isha"`
- `"After Isha"`

---

## Automation Examples

### Play Athan at Prayer Time

```yaml
automation:
  - alias: "Play Athan at Fajr"
    trigger:
      - platform: state
        entity_id: sensor.muslim_prayer_companion_home_fajr_prayer
    condition:
      - condition: template
        value_template: "{{ now().strftime('%H:%M') == states('sensor.muslim_prayer_companion_home_fajr_prayer') | as_timestamp | timestamp_custom('%H:%M') }}"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room_speaker
        data:
          media_content_id: "http://your-server/athan.mp3"
          media_content_type: "music"
```

### Pre-Prayer Notification (15 Minutes Before)

```yaml
automation:
  - alias: "Notify 15 Minutes Before Prayer"
    trigger:
      - platform: numeric_state
        entity_id: sensor.muslim_prayer_companion_home_next_prayer_minutes
        below: 16
        above: 14
    action:
      - service: notify.mobile_app
        data:
          title: "Prayer Reminder"
          message: "{{ states('sensor.muslim_prayer_companion_home_next_prayer_countdown') }}"
```

### Dim Lights During Prayer Time

```yaml
automation:
  - alias: "Dim Lights for Prayer"
    trigger:
      - platform: time
        at: sensor.muslim_prayer_companion_home_next_prayer
    action:
      - service: light.turn_on
        target:
          entity_id: light.prayer_room
        data:
          brightness_pct: 30
      - delay:
          minutes: 15
      - service: light.turn_on
        target:
          entity_id: light.prayer_room
        data:
          brightness_pct: 100
```

### Ramadan Suhoor Reminder

```yaml
automation:
  - alias: "Suhoor Reminder"
    trigger:
      - platform: template
        value_template: >
          {{ states('sensor.muslim_prayer_companion_home_is_ramadan') == 'true' and
             (as_timestamp(states('sensor.muslim_prayer_companion_home_fajr_prayer')) - as_timestamp(now())) | int < 1800 and
             (as_timestamp(states('sensor.muslim_prayer_companion_home_fajr_prayer')) - as_timestamp(now())) | int > 1740 }}
    action:
      - service: notify.all
        data:
          title: "Suhoor Reminder"
          message: "30 minutes until Fajr. Time to complete Suhoor!"
```

### Friday Jumu'a Reminder

```yaml
automation:
  - alias: "Jumu'a Reminder"
    trigger:
      - platform: time
        at: "11:00:00"
    condition:
      - condition: state
        entity_id: sensor.muslim_prayer_companion_home_is_friday
        state: "true"
    action:
      - service: notify.mobile_app
        data:
          title: "Jumu'a Today"
          message: "Friday prayer at {{ states('sensor.muslim_prayer_companion_home_jumu_a_time') | as_timestamp | timestamp_custom('%H:%M') }}"
```

---

## Architecture

### System Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Config Flow   │────▶│   Coordinator    │────▶│    Sensors      │
│  (Multi-step)   │     │  (Per Entry)     │     │  (30+ types)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   API Providers      │
                    ├──────────────────────┤
                    │ • CalculatedProvider │
                    │ • IrelandProvider    │
                    │ • (Your Custom)      │
                    └──────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Standardized Data   │
                    ├──────────────────────┤
                    │ • PrayerTimesData    │
                    │ • IqamahTimesData    │
                    │ • MosqueInfo         │
                    └──────────────────────┘
```

### Data Flow

1. **Configuration**: User configures via multi-step flow (source → location → method)
2. **Provider Selection**: Coordinator selects appropriate provider based on config
3. **Data Fetching**: Provider fetches prayer times from API or calculates them
4. **Normalization**: Raw data is converted to standardized `PrayerTimesData`
5. **Validation**: Data is validated (times in order, timezone-aware)
6. **Enhancement**: Coordinator adds Hijri dates, countdown, Qibla direction
7. **Sensor Update**: Sensors read from coordinator data
8. **Scheduling**: Next update scheduled for midnight

### Multi-Instance Support

Each config entry creates its own:

- **Coordinator**: Independent data fetching and caching
- **Device**: Groups all sensors for that location
- **Sensors**: Unique IDs in format `{sensor_key}_{entry_id}`

This allows:

- Multiple locations (home, office, mosque)
- Different calculation methods per location
- Independent refresh cycles

---

## Creating Custom API Providers

You can create custom providers to integrate with any prayer times API.

### Step 1: Create Provider File

Create a new file in `api_providers/`:

```python
# api_providers/my_custom.py

"""Custom prayer times provider for MyMosque API."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

import aiohttp

from .base import (
    IqamahTimesData,
    MosqueInfo,
    PrayerTimesData,
    PrayerTimesProvider,
    ProviderConfig,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderValidationError,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

LOGGER = logging.getLogger(__name__)


class MyCustomProvider(PrayerTimesProvider):
    """Provider for MyMosque API."""

    name = "my_custom"

    def __init__(self, config: ProviderConfig, session: ClientSession | None = None):
        """Initialize the provider."""
        super().__init__(config, session)
        self._api_url = "https://api.mymosque.com/prayer-times"

    async def async_fetch_prayer_times(self, target_date: date) -> PrayerTimesData:
        """Fetch prayer times from the API.

        Args:
            target_date: The date to fetch times for.

        Returns:
            PrayerTimesData with all times in UTC.

        Raises:
            ProviderConnectionError: If API request fails.
            ProviderResponseError: If response is invalid.
            ProviderValidationError: If times fail validation.
        """
        LOGGER.debug("Fetching prayer times from MyMosque API for %s", target_date)

        # Build API URL with parameters
        url = f"{self._api_url}?lat={self.config.latitude}&lon={self.config.longitude}&date={target_date}"

        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise ProviderConnectionError(f"API returned status {response.status}")
                json_data = await response.json()
        except aiohttp.ClientError as err:
            raise ProviderConnectionError(f"Failed to connect: {err}") from err

        LOGGER.debug("Raw API response: %s", json_data)

        # Parse the response into PrayerTimesData
        try:
            prayer_data = self._parse_response(json_data, target_date)
        except (KeyError, ValueError) as err:
            raise ProviderResponseError(f"Invalid response format: {err}") from err

        # Validate the data
        try:
            prayer_data.validate()
        except AssertionError as err:
            raise ProviderValidationError(f"Validation failed: {err}") from err

        return prayer_data

    def _parse_response(self, json_data: dict, target_date: date) -> PrayerTimesData:
        """Parse API response into standardized format.

        This is where you map the API's field names to standard fields.
        All times must be converted to UTC timezone-aware datetime objects.
        """
        def parse_time(time_str: str) -> datetime:
            """Convert 'HH:MM' to UTC datetime."""
            hour, minute = map(int, time_str.split(":"))
            return datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=hour,
                minute=minute,
                tzinfo=timezone.utc,  # IMPORTANT: Must be timezone-aware
            )

        # Map API fields to standard fields
        # Adjust these based on your API's response format
        return PrayerTimesData(
            fajr=parse_time(json_data["fajr"]),
            sunrise=parse_time(json_data["sunrise"]),
            dhuhr=parse_time(json_data["dhuhr"]),
            asr=parse_time(json_data["asr"]),
            maghrib=parse_time(json_data["maghrib"]),
            isha=parse_time(json_data["isha"]),
            midnight=parse_time(json_data.get("midnight", "00:00")),
        )

    async def async_fetch_iqamah_times(self, target_date: date) -> IqamahTimesData | None:
        """Fetch iqamah times if your API supports them."""
        # Return None if not supported, or implement similar to prayer times
        return None

    @property
    def supports_iqamah(self) -> bool:
        """Return True if this provider supports iqamah times."""
        return False

    @property
    def supports_mosque_search(self) -> bool:
        """Return True if this provider supports mosque search."""
        return False
```

### Step 2: Register the Provider

Update `api_providers/__init__.py`:

```python
from .my_custom import MyCustomProvider

__all__ = [
    # ... existing exports
    "MyCustomProvider",
]
```

### Step 3: Add to Coordinator

Update `coordinator.py` to use your provider:

```python
from .api_providers import MyCustomProvider

# In _get_provider method:
if source_type == "my_custom":
    self._provider = MyCustomProvider(config, self._session)
```

### Step 4: Add Configuration

Update `const.py`:

```python
SOURCE_MY_CUSTOM: Final = "my_custom"

MY_CUSTOM_CALC_METHODS: Final = {
    "MyMosque - Main Branch": "my-main",
    "MyMosque - North Branch": "my-north",
}
```

Update `config_flow.py` to include your source type option.

### Data Model Reference

#### PrayerTimesData

**Required fields** (all must be UTC timezone-aware datetime):

```python
fajr: datetime       # Dawn prayer
sunrise: datetime    # Sunrise
dhuhr: datetime      # Noon prayer
asr: datetime        # Afternoon prayer
maghrib: datetime    # Sunset prayer
isha: datetime       # Night prayer
```

**Optional fields:**

```python
midnight: datetime | None   # Islamic midnight
imsak: datetime | None      # Suhoor end time (must be before fajr)
sunset: datetime | None     # Defaults to maghrib if not set
```

**Validation rules:**

- All times must be timezone-aware (have tzinfo set)
- Times must be in chronological order: fajr < sunrise < dhuhr < asr < maghrib < isha
- Imsak must be before fajr

#### IqamahTimesData

**All fields optional** (UTC timezone-aware datetime):

```python
fajr: datetime | None
dhuhr: datetime | None
asr: datetime | None
maghrib: datetime | None
isha: datetime | None
juma: datetime | None           # Friday prayer
juma_khutbah: datetime | None   # Khutbah start time
```

#### MosqueInfo

```python
name: str              # Required: Mosque name
uuid: str              # Required: Unique identifier
latitude: float        # Required: Latitude
longitude: float       # Required: Longitude
address: str | None    # Street address
city: str | None       # City name
country: str | None    # Country name
website: str | None    # Website URL
timezone: str | None   # Timezone (e.g., "Europe/Dublin")
```

---

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/amaharek/muslim_prayer_companion.git
cd muslim_prayer_companion

# Install UV (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run tests
uv run pytest -v

# Run with coverage
uv run pytest --cov custom_components/muslim_prayer_companion -v

# Lint and format
uv run ruff format .
uv run ruff check . --fix

# Run pre-commit hooks
uv run pre-commit run --all-files
```

### Project Structure

```
muslim_prayer_companion/
├── custom_components/muslim_prayer_companion/
│   ├── __init__.py              # Entry point, migration
│   ├── config_flow.py           # Configuration UI
│   ├── const.py                 # Constants
│   ├── coordinator.py           # Data coordinator
│   ├── sensor.py                # Sensor definitions
│   ├── manifest.json            # Integration manifest
│   ├── api_providers/           # Provider abstraction
│   │   ├── base.py              # Base classes
│   │   ├── calculated.py        # Library-based calculation
│   │   └── ireland.py           # Ireland APIs
│   ├── helpers/                 # Utilities
│   │   ├── hijri.py             # Hijri conversion
│   │   ├── qibla.py             # Qibla calculation
│   │   └── special_dates.py     # Special date detection
│   └── translations/            # UI translations
├── tests/                       # Test suite
├── pyproject.toml               # Project configuration
└── README.md                    # This file
```

---

## Troubleshooting

### Common Issues

#### Sensors show "Unknown" or "Unavailable"

1. Check your internet connection (for API-based methods)
2. Verify coordinates are correct in your Home Assistant settings
3. Check the Home Assistant logs for error messages
4. Try reloading the integration

#### Prayer times are wrong

1. Verify your calculation method matches your location/school of thought
2. Check if your timezone is correctly set in Home Assistant
3. For Ireland methods, ensure the mosque API is accessible

#### Multiple entries showing same data

Each entry should have unique coordinates or calculation methods. Check that you've configured different locations.

### Debug Logging

Enable debug logging by adding to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.muslim_prayer_companion: debug
```

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/amaharek/muslim_prayer_companion/issues)
- **Discussions**: [GitHub Discussions](https://github.com/amaharek/muslim_prayer_companion/discussions)

---

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [prayer-times-calculator](https://pypi.org/project/prayer-times-calculator/) library
- [hijri-converter](https://pypi.org/project/hijri-converter/) library
- Home Assistant community
- Irish mosque communities for API access

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[commits]: https://github.com/amaharek/muslim_prayer_companion/commits/main
[license-shield]: https://img.shields.io/github/license/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[releases]: https://github.com/amaharek/muslim_prayer_companion/releases
[downloads-shield]: https://img.shields.io/github/downloads/amaharek/muslim_prayer_companion/total.svg?style=for-the-badge
[downloads]: https://github.com/amaharek/muslim_prayer_companion/releases
