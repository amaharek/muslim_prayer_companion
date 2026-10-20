# Changelog

All notable changes to Muslim Prayer Companion are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows [Semantic Versioning](https://semver.org/).

## [4.0.0] - 2026-10-20

### Added

- Mosque registry `custom_components/muslim_prayer_companion/data/mosques.json`: Irish mosques are data records, not code. New mosque: Muslim Association of Ireland, Tallaght (`ie-mai`), whose daily times are read from its public website (maionline.ie); its Jumu'ah times are entered manually.
- Friday prayers: a list of mosques per entry (**Configure → Friday prayers**), each with its own device and two **Jumu'ah 1/2** timestamp sensors. Times are published automatically for MCND, HICC and SDIC (the API's `jumuah` and `jumuah_label` lists) or entered manually; manual times also serve as fallback. `juma_time` is kept as an alias and is now available every day.
- Options menu with five pages: Calculation method, Iqamah times, Friday prayers, Hijri date and Imsak, Sensors and display.
- Reconfigure flow to change the mosque, the location or the source without recreating the entry.
- Unique IDs per mosque (`ireland:<key>`) and per location (`calculated:<lat>,<lon>`); the same mosque cannot be added twice.
- Iqamah methods `offset`, `mosque`, `api` and `disabled`, with per-prayer offsets and a custom JSON URL; Iqamah sensors keep today's time until it passes even after the prayer has started.
- Hijri adjustment (−2 to +2 days) and the option to change the Hijri day at Maghrib; configurable Imsak minutes before Fajr.
- Sensor groups that can be switched off (Iqamah, Hijri, countdown, Qibla, special dates, Friday), countdown formats (sentence, clock, short) and a prayer window for `current_prayer_period`.
- New sensors `ramadan_day`, `days_until_ramadan`, `upcoming_islamic_event` (attributes `date`, `days_until`), `imsak` and `iftar`.
- `source` attribute on every prayer-time sensor (`icci-timetable`, `mcnd-api`, `hicc-api`, `sdic-api`, `mai-website`, `calculated:<method>`, `calculated-fallback:isna`) and on the Iqamah sensors (`offset`, `mosque`, `api`).
- Repairs issue plus calculated ISNA fallback when a mosque source fails: nothing is silent and nothing goes unavailable. One warning when entering fallback, one info line on recovery, retries with increasing delays.
- Event `muslim_prayer_companion_event` (types `prayer`, `iqamah`, `imsak`, `jumuah`; fields `type`, `entry_id`, `location_name`, `time`, plus `prayer` or `mosque`/`slug`/`session`/`label`) fired at the exact minute.
- Action `muslim_prayer_companion.get_prayer_times` (`config_entry_id`, `date`, `days` 1–366) with a response; mosque APIs answer for today and tomorrow only.
- Per-minute recomputation of the countdown, next prayer, current period and Hijri date without network access; refresh at local midnight.
- Diagnostics download (coordinates and custom URL redacted).
- Arabic translations for everything, including entity names, selector options, the Repairs issue and the action.
- Nine more calculation methods: `moonsighting`, `dubai`, `jakim`, `tunisia`, `algeria`, `kemenag`, `morocco`, `portugal`, `jordan` (23 in total).
- Weekly GitHub Action (`.github/workflows/mosque-health.yml`, `scripts/check_mosques.py`) that fetches and parses every mosque source and opens or updates an issue when one breaks.
- `scripts/build_icci_timetable.py` with `--check` and `--download` to verify or rebuild the bundled ICCI timetable.
- hassfest in CI; tests run against Home Assistant 2025.2.4 (the minimum) and the latest release.

### Changed

- Calculations use `prayer-times-calculator-offline==1.0.3`, the library behind Home Assistant's core Islamic Prayer Times integration, instead of `prayer-times-calculator` (which fetched from api.aladhan.com). Calculated entries make no network requests at all.
- `hijridate==2.3.0` replaces `hijri-converter`; Hijri dates are computed offline.
- `iot_class` is `calculated`, `integration_type` is `service`.
- Config entry version 3, with migration from version 1 (3.0.x) and version 2.
- **Migration note:** in 3.0.x the calculation method chosen in the UI was ignored and every entry effectively used ICCI times. 4.0.0 honours the stored method (options first, as 3.0.x read it), so prayer times may change after upgrading; check the entry's Configure or Reconfigure. The previously stored but never applied `enable_hijri` and `enable_countdown` toggles now disable those sensor groups. Entity unique IDs (`{key}_{entry_id}`) are unchanged, so history and automations survive.
- ICCI DST rule: the table's clock is fixed (UTC+1 from 1 April to 31 October, UTC+0 otherwise) and converted deterministically, instead of the 3.0.1 comparison with local sunset.
- Midnight is the midpoint of Maghrib and the next day's sunrise, floored to the minute, for every source.
- Daily Prayer Time (dpt) mosques use the API's `tomorrow`, `*_jamah` and `jumuah` fields; one HTTP request per refresh serves prayer times, Iqamah and Friday prayers (payload cached for 10 minutes).
- `special_night` is `unknown` instead of an empty string when there is no special night; `current_prayer_period` shows the prayer's name during the prayer window.
- Options changes reload the entry.
- Minimum Home Assistant 2025.2.4; Python 3.13 for development. pre-commit uses ruff instead of black, isort and pyupgrade.

### Fixed

- Mosque and calculated times are converted from local time to UTC correctly. (The unreleased rewrite this release is based on labelled Irish clock times as UTC; 3.0.x parsed them as naive local times.)
- `current_prayer_period` was always `Before Fajr` in the unreleased rewrite.
- A blocking network call in the event loop (the online calculator) made every calculated update fail on recent Home Assistant versions.
- The options dialog crashed on Home Assistant 2025.12 and newer.
- Isha later than midnight and Midnight before Maghrib are placed on the right day.
- `Night before Eid al-Fitr` could never be shown on 29 Ramadan; it now follows the real month length.

### Removed

- `hijri-converter` and the online `prayer-times-calculator` requirements.
- The `icon` key in `manifest.json` and the `domains` key in `hacs.json` (neither is part of the schemas).
- The MagicMock-based test helpers; tests run on the Home Assistant test harness.

## [3.0.1] - 2026-10-20

### Fixed

- `ie-icci` prayer times silently fell back to the ISNA calculation. `https://islamireland.ie/api/timetable/` now returns the new ICCI website's HTML page instead of JSON.

### Changed

- `ie-icci` times now come from ICCI's own perpetual timetable, bundled in `custom_components/muslim_prayer_companion/data/icci_timetable.json` (from the [2 August 2022 Wayback Machine snapshot](https://web.archive.org/web/20220802110619id_/https://islamireland.ie/api/timetable/)). The `ie-icci` prayer times no longer make any network request.
- DST correction: the timetable changes clocks on 1 April and 1 November. Days where its Maghrib is more than 30 minutes off Home Assistant's local sunset are shifted by one hour, e.g. 30 Mar 2027 and 25–31 Oct 2026.
- `ie-icci` Midnight is now the midpoint between Maghrib and the next day's sunrise from the same timetable, instead of the ISNA calculation.
- If the bundled timetable is missing or corrupt, one warning is logged and `ie-icci` falls back to the ISNA calculation.
- `manifest.json` version is now in step with the release (the 3.0.0 release still said 2.2.0).

## [3.0.0] - 2025-03-18

- Single-coordinator architecture with the `ie-icci`, `ie-mcnd` and `ie-hicc` methods, Iqamah offsets and the Hijri date fetched from aladhan. The calculation method chosen in the UI was not applied (see the 4.0.0 migration note).

Older releases: see the [GitHub releases](https://github.com/amaharek/muslim_prayer_companion/releases).

[4.0.0]: https://github.com/amaharek/muslim_prayer_companion/releases/tag/4.0.0
[3.0.1]: https://github.com/amaharek/muslim_prayer_companion/releases/tag/3.0.1
[3.0.0]: https://github.com/amaharek/muslim_prayer_companion/releases/tag/3.0.0
