# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Muslim Prayer Companion is a Home Assistant (HACS) custom integration: prayer times (calculated offline or from an Irish mosque's published source), Iqamah times, Friday prayers for several mosques, Hijri calendar, countdown and special-date sensors, events and a `get_prayer_times` action.

**Stack**: Python 3.13, Home Assistant custom component (minimum Home Assistant 2025.2.4), pip/venv

**Version**: 4.0.0

## Common Commands

```bash
# Set up (or run scripts/setup)
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests
pytest -q --cov
pytest tests/test_coordinator.py -q
pytest tests/test_icci_timetable.py -q -k dst

# Lint and format (ruff replaces black/isort/pyupgrade)
ruff check . --fix
ruff format .
pre-commit run --all-files

# Bundled data
python -I scripts/build_icci_timetable.py --check     # verify data/icci_timetable.json
python -I scripts/build_icci_timetable.py --download  # rebuild from the Wayback snapshot
python scripts/check_mosques.py                       # fetch and parse every mosque source
python scripts/check_mosques.py --offline             # registry and bundled data only

# Local development (runs Home Assistant with the integration)
scripts/develop
```

## Architecture

```
Config flow → Config entry (data = identity, options = settings) → Coordinator (per entry) → Sensors
                                                                        │
                                              providers (one ProviderResult per fetch)
```

### Layout

```
custom_components/muslim_prayer_companion/
├── __init__.py              # Setup, unload, remove_entry, device removal, migration to v3, get_prayer_times action
├── config_flow.py           # Setup (source → mosque | location → method), reconfigure, options menu (5 pages)
├── const.py                 # Keys, defaults, groups, 23 calculation methods
├── coordinator.py           # Fetch → fallback + Repairs → derived data; per-minute tick; events; midnight refresh; retry
├── sensor.py                # Descriptions with translation_key + group; Friday sensors/devices; stale-entity cleanup
├── diagnostics.py
├── services.yaml
├── manifest.json            # requirements: prayer-times-calculator-offline==1.0.3, hijridate==2.3.0
├── strings.json             # byte-identical copy of translations/en.json
├── data/
│   ├── mosques.json         # Mosque registry (the only place mosques are defined)
│   └── icci_timetable.json  # ICCI perpetual table (verified by SHA-256 in tests)
├── api_providers/
│   ├── base.py              # PrayerTimesData, IqamahTimesData, JumuahTime, ProviderResult, PrayerTimesProvider
│   ├── calculated.py        # prayer-times-calculator-offline (iso8601 UTC output), runs in a thread
│   ├── ireland.py           # IrelandProvider: dispatch on registry source type, payload cache (10 min)
│   ├── icci_timetable.py    # Bundled table: fixed clock rule (UTC+1 Apr–Oct), Midnight midpoint
│   ├── dpt.py               # Daily Prayer Time plugin parser (today, tomorrow, jamah, jumuah)
│   ├── mai.py               # maionline.ie homepage parser (today only, strict six labels)
│   └── http.py              # fetch_text/fetch_json with error mapping (HTML-with-200 → ProviderResponseError)
├── helpers/
│   ├── registry.py          # Loads mosques.json at import; MOSQUES, MOSQUE_KEYS, distance helpers
│   ├── settings.py          # Settings.from_entry, default_options, entry_unique_id
│   ├── derived.py           # compute_derived(): the whole data dict, pure
│   ├── friday.py            # FridayMosqueConfig, validation, next_friday_occurrence, FridayPrayersFetcher
│   ├── iqamah.py            # offsets, custom JSON API client
│   ├── hijri.py             # hijridate wrapper, adjustment, Maghrib rollover
│   ├── special_dates.py     # Ramadan, special nights, upcoming events (take a HijriDate)
│   └── qibla.py
└── translations/            # en.json, ar.json (same key set, tested)
```

### Data flow

1. The config flow stores identity in `entry.data` (`source_type`, `calculation_method` = method or mosque key, coordinates, name, timezone) and everything changeable in `entry.options`. Options pages save the full merged dict and reload the entry (no update listener).
2. `Settings.from_entry()` gives the coordinator a typed view with defaults.
3. The provider's `async_fetch(today)` returns a `ProviderResult` (today, tomorrow, iqamah, jumuah, source). All datetimes are UTC; mosque clock times are interpreted in the mosque's zone.
4. On `ProviderError` (or any exception) from a mosque source the coordinator fetches from a `CalculatedProvider` (ISNA, same coordinates), relabels `source` to `calculated-fallback:isna` and opens the Repairs issue `provider_fallback_<entry_id>`; recovery closes it. If that fails too, today's last result is kept, else `UpdateFailed` with retry (60/120/300/600 s).
5. `compute_derived()` builds the data dict (next occurrences, next prayer/countdown, period, iqamah, Hijri, special dates, Friday, source). It runs after every fetch and on every minute tick; the tick also fires `muslim_prayer_companion_event` for instants that passed since the last tick.
6. Sensors read the dict. Friday sensors read `data["friday"][slug]`.

### Conventions

- Entity unique*ids are `{key}*{entry*id}`(unchanged since 2.x) and`friday*{slug}_jumuah_{n}\_{entry_id}`. Never change keys.
- Mosques are added in `data/mosques.json` plus translation labels (`selector.ireland_mosque.options`, `selector.friday_source.options`); see CONTRIBUTING.md. A new source type needs a parser module, a branch in `IrelandProvider.async_fetch` and a type in `helpers/registry.py`.
- Providers never import Home Assistant and never create their own aiohttp session (tests mock `async_get_clientsession`).
- `strings.json` must stay identical to `translations/en.json`; `ar.json` must have the same keys (tests check both).
- Keep `manifest.json` requirements pinned and equal to `pyproject.toml` dependencies (tested).

## Testing

```bash
pytest -q                      # everything (~280 tests)
pytest -q --cov --cov-report=term-missing
pytest tests/test_config_flow.py -q -k friday
```

```
tests/
├── conftest.py                 # hass in Dublin, make_entry(), setup_entry(), advance()/move_to(), fixture loaders,
│                               # aioclient_mock for all mosque sites, freezegun shim for the offline calculator
├── fixtures/                   # dpt_{mcnd,hicc,sdic}.json, mai_home.html, mai_home_evening.html (captured 20 Oct 2026)
├── test_init.py                # setup/unload, service registration
├── test_coordinator.py         # tick, events, midnight, fallback + Repairs, retry, MAI, HICC end to end
├── test_config_flow.py         # setup, duplicates, reconfigure, every options page, Friday add/edit/remove
├── test_migration.py           # v1/v2 → v3, unique_id collisions, migrate_options()
├── test_sensor.py              # legacy keys, translation keys, groups, Friday devices and cleanup
├── test_services.py            # get_prayer_times
├── test_derived.py             # compute_derived table-driven
├── test_friday.py / test_iqamah.py / test_hijri.py / test_special_dates.py
├── test_icci_timetable.py      # raw rows, SHA-256, DST rule, Midnight, corrupt file
├── test_registry.py / test_translations.py / test_manifest.py / test_diagnostics.py
└── api_providers/              # test_base, test_calculated, test_dpt, test_mai
```

Time is controlled with the `freezer` fixture; `FROZEN_NOW` is 2026-10-20 11:00 UTC (12:00 Irish time). Use `advance(hass, freezer, delta)` to trigger timers: the coordinator's interval refresh is a background task, so a plain `async_block_till_done()` is not enough. Move the clock a few seconds past an interval boundary.

## Dependencies

**Runtime**: `prayer-times-calculator-offline==1.0.3`, `hijridate==2.3.0` (aiohttp comes from Home Assistant)
**Dev**: `homeassistant>=2025.2.4`, `pytest-homeassistant-custom-component>=0.13.214`, `ruff==0.17.1`, `pre-commit`, `codespell`, `yamllint`
