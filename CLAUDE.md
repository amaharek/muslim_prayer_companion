# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Muslim Prayer Companion is a Home Assistant (HACS) custom integration that provides accurate prayer times, Iqamah times, Hijri calendar information, and Islamic companion features as sensors.

**Stack**: Python 3.12+, UV (package manager), Home Assistant custom component

**Version**: 3.0.0 (Multi-instance support, API provider abstraction)

## Common Commands

```bash
# Install dependencies (using UV)
uv sync

# Run tests
uv run pytest --cov custom_components/tests/ -v

# Run specific test file
uv run pytest tests/api_providers/test_ireland.py -v

# Lint and format
uv run ruff format .
uv run ruff check . --fix
uv run pre-commit run --all-files

# Local development (runs Home Assistant with integration)
scripts/develop
```

## Architecture

The integration follows Home Assistant's standard pattern with multi-instance support:

```
Config Flow → Config Entry → Coordinator (per entry) → Sensors
```

### Key Components

```
custom_components/muslim_prayer_companion/
├── __init__.py              # Entry point, migration handler
├── config_flow.py           # Multi-step configuration UI
├── const.py                 # Constants, method definitions
├── coordinator.py           # Data coordinator using providers
├── sensor.py                # 30+ sensor entities
├── api_providers/           # Provider abstraction layer
│   ├── base.py              # Abstract base classes, data models
│   ├── calculated.py        # prayer-times-calculator wrapper
│   └── ireland.py           # ICCI, MCND, HICC, SDIC APIs
├── helpers/                 # Utility modules
│   ├── hijri.py             # Hijri date utilities
│   ├── qibla.py             # Qibla direction calculation
│   └── special_dates.py     # Ramadan, Eid, special nights
└── translations/            # UI translations (en, ar)
```

### Data Flow

1. User configures via multi-step config flow (source type → location → method)
2. Coordinator creates appropriate provider (Calculated or Ireland)
3. Provider fetches prayer times, returns standardized `PrayerTimesData`
4. Coordinator computes Iqamah times, Hijri date, next prayer
5. Sensors expose data to Home Assistant
6. Coordinator schedules next update at midnight

### Multi-Instance Pattern

Each config entry has its own coordinator stored in `entry.runtime_data`:

- Supports multiple locations/mosques simultaneously
- Each entry has unique sensor IDs: `{key}_{entry_id}`
- Backward compatible with v1 config entries (auto-migration)

### API Providers

| Provider             | Source                      | Features                                      |
| -------------------- | --------------------------- | --------------------------------------------- |
| `CalculatedProvider` | prayer-times-calculator lib | 14 standard methods (ISNA, MWL, etc.)         |
| `IrelandProvider`    | ICCI, MCND, HICC, SDIC APIs | Ireland mosque times, iqamah (WordPress APIs) |

### Key Data Models

```python
PrayerTimesData  # Standardized prayer times (UTC datetime)
IqamahTimesData  # Iqamah times with validation
MosqueInfo       # Mosque metadata
ProviderConfig   # Provider configuration
```

### Sensors

**Prayer Times**: Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha, Midnight
**Iqamah Times**: iqamah_Fajr, iqamah_Dhuhr, iqamah_Asr, iqamah_Maghrib, iqamah_Isha
**Hijri Date**: hijri_date, hijri_day, hijri_month_readable, hijri_year, etc.
**Next Prayer**: next_prayer, next_prayer_name, next_prayer_countdown, next_prayer_minutes
**Additional**: qibla_direction, current_prayer_period, juma_time, is_ramadan, is_friday, special_night

## Testing

```bash
# Run all tests
uv run pytest -v

# Run with coverage
uv run pytest --cov custom_components/muslim_prayer_companion -v

# Run specific test class
uv run pytest tests/api_providers/test_base.py::TestPrayerTimesData -v

# Run with debug logging
uv run pytest -v --log-cli-level=DEBUG
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_integration.py      # Full integration tests
├── test_migration.py        # Config entry migration tests
├── test_sensor_formats.py   # Sensor value format validation
├── test_helpers.py          # Test utility functions
└── api_providers/           # Provider tests
    ├── test_base.py         # Data model validation
    └── test_ireland.py      # Ireland API tests
```

## Configuration Constants

**Source Types**: `calculated`, `ireland`
**Standard Methods**: isna, mwl, karachi, makkah, egypt, tehran, gulf, etc.
**Ireland Methods**: ie-icci, ie-mcnd, ie-hicc, ie-sdic

## Dependencies

**Runtime**: `prayer-times-calculator`, `hijri-converter`, `aiohttp` (from HA)
**Dev**: `homeassistant`, `pytest-homeassistant-custom-component`, `ruff`, `pre-commit`
