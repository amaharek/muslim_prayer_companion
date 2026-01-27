# Changelog

All notable changes to Muslim Prayer Companion are documented in this file.

## [3.0.0] - 2025-01-27

### Major Release: Multi-Instance Support & API Provider Abstraction

This release introduces multi-mosque/multi-location support, a clean API provider abstraction layer, and many new sensors while maintaining **full backward compatibility** with existing installations.

---

## Summary of Changes

### New Features

#### Multi-Instance Support
- **Multiple locations/mosques**: Add the integration multiple times for different locations
- **Per-entry configuration**: Each config entry has its own coordinator and sensors
- **Unique sensor IDs**: Format `{sensor_key}_{entry_id}` ensures no conflicts

#### New Sensors (11 added)
| Sensor | Type | Description |
|--------|------|-------------|
| `next_prayer_countdown` | String | "Asr in 45 minutes" |
| `next_prayer_minutes` | Number | Minutes until next prayer |
| `juma_time` | Timestamp | Friday prayer time (available on Fridays) |
| `current_prayer_period` | String | "Between Dhuhr and Asr" |
| `qibla_direction` | Number (°) | Degrees from North to Mecca |
| `location_name` | String | Configured location name |
| `is_ramadan` | Boolean | True during Ramadan |
| `is_friday` | Boolean | True on Fridays |
| `special_night` | String | Laylatul Qadr, etc. |

#### Multi-Step Config Flow
1. **Source Selection**: Choose between calculated times or Ireland mosque API
2. **Location Setup**: Use Home Assistant location or enter custom coordinates
3. **Method Selection**: Pick calculation method (ISNA, MWL, etc.)

#### Arabic Translation
- Added `translations/ar.json` for Arabic-speaking users

---

## Architecture Changes

### New: API Provider Abstraction (`api_providers/`)

Created a clean abstraction layer for prayer times data sources:

```
api_providers/
├── __init__.py          # Package exports
├── base.py              # Abstract base classes & data models
├── calculated.py        # prayer-times-calculator wrapper
└── ireland.py           # ICCI, MCND, HICC, SDIC unified provider
```

**Data Models** (with validation):
- `PrayerTimesData`: Standardized prayer times (UTC datetime)
- `IqamahTimesData`: Iqamah times with optional Jumu'a
- `MosqueInfo`: Mosque metadata
- `ProviderConfig`: Provider configuration

**Provider Interface**:
```python
class PrayerTimesProvider(ABC):
    async def async_fetch_prayer_times(date) -> PrayerTimesData
    async def async_fetch_iqamah_times(date) -> IqamahTimesData | None
    async def async_search_mosques(lat, lon, radius) -> list[MosqueInfo]
```

### New: Helper Modules (`helpers/`)

```
helpers/
├── __init__.py          # Package exports
├── hijri.py             # Hijri date conversion (using hijri-converter)
├── qibla.py             # Qibla direction calculation
└── special_dates.py     # Ramadan, Eid, special night detection
```

---

## File-by-File Changes

### Modified Files

| File | Changes |
|------|---------|
| `__init__.py` | Multi-instance support, `entry.runtime_data` storage, config migration handler |
| `coordinator.py` | Complete rewrite using provider abstraction, location parameters, enhanced logging |
| `sensor.py` | 11 new sensors, multi-instance unique IDs, icons for all sensors |
| `config_flow.py` | Multi-step flow, options flow, source type selection |
| `const.py` | New constants for source types, locations, expanded method definitions |
| `manifest.json` | Version bump to 3.0.0 |
| `translations/en.json` | Updated for multi-step config flow |
| `pyproject.toml` | Migrated from Poetry to UV format |
| `CLAUDE.md` | Updated architecture documentation |

### New Files

| File | Purpose |
|------|---------|
| `api_providers/__init__.py` | Package initialization |
| `api_providers/base.py` | Abstract base classes, data models with validation |
| `api_providers/calculated.py` | prayer-times-calculator library wrapper |
| `api_providers/ireland.py` | Unified Ireland mosque API provider |
| `helpers/__init__.py` | Package initialization |
| `helpers/hijri.py` | Hijri date utilities |
| `helpers/qibla.py` | Qibla direction calculation |
| `helpers/special_dates.py` | Special Islamic date detection |
| `translations/ar.json` | Arabic translation |
| `tests/conftest.py` | Shared test fixtures |
| `tests/test_migration.py` | Config entry migration tests |
| `tests/test_sensor_formats.py` | Sensor value format validation |
| `tests/api_providers/__init__.py` | Test package |
| `tests/api_providers/test_base.py` | Data model validation tests |
| `tests/api_providers/test_ireland.py` | Ireland API tests |

### Removed Files

| File | Reason |
|------|--------|
| `poetry.lock` | Migrated to UV package manager |

---

## Config Entry Migration

Existing v1 config entries are automatically migrated to v2:

**Added fields**:
- `latitude`: From Home Assistant config
- `longitude`: From Home Assistant config
- `location_name`: Default "Home"
- `source_type`: Auto-detected from calculation method
- `timezone`: From Home Assistant config

**Preserved fields**:
- `calculation_method`: Unchanged
- All existing options

---

## Backward Compatibility

### Guaranteed Preserved
- ✅ Sensor unique_ids: `{key}_{entry_id}` format unchanged
- ✅ Entity names: All original sensors retain their names
- ✅ Calculation method values: `isna`, `ie-icci`, etc. unchanged
- ✅ Automations: All existing triggers and conditions work
- ✅ Dashboard cards: No changes needed

### Migration is Automatic
- v1 config entries auto-upgrade to v2 on first load
- No user action required

---

## Package Management

Migrated from **Poetry** to **UV** for faster dependency resolution:

```bash
# Old (Poetry)
poetry install
poetry run pytest

# New (UV)
uv sync
uv run pytest
```

---

## Testing

### New Test Coverage

```
tests/
├── conftest.py              # Shared fixtures
├── test_integration.py      # Updated for new architecture
├── test_migration.py        # Config entry migration tests
├── test_sensor_formats.py   # Sensor value format validation
├── test_helpers.py          # Updated utility functions
└── api_providers/
    ├── test_base.py         # Data model validation
    └── test_ireland.py      # Ireland API response parsing
```

### Run Tests
```bash
uv run pytest -v
uv run pytest --cov custom_components/muslim_prayer_companion -v
```

---

## Ireland API Support

### Supported Mosques
| API Key | Mosque | Type |
|---------|--------|------|
| `ie-icci` | Islamic Cultural Centre of Ireland | Custom API |
| `ie-mcnd` | Muslim Community North Dublin | WordPress DPT |
| `ie-hicc` | Hansfield Islamic Cultural Centre | WordPress DPT |
| `ie-sdic` | South Dublin Islamic Centre | WordPress DPT |

### WordPress APIs Include
- Prayer times (fajr_begins, zuhr_begins, etc.)
- Iqamah times (fajr_jamah, zuhr_jamah, etc.)
- Jumu'a time

---

## Breaking Changes

**None** - This release maintains full backward compatibility.

---

## Dependencies

### Runtime
- `prayer-times-calculator>=0.0.12`
- `hijri-converter>=2.3.1`
- `aiohttp` (provided by Home Assistant)

### Development
- `homeassistant>=2024.10.3`
- `pytest>=7.0`
- `pytest-asyncio>=0.21`
- `pytest-homeassistant-custom-component>=0.13.174`
- `ruff>=0.9`
- `pre-commit>=3.0`
