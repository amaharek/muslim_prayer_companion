# Changelog

All notable changes to Muslim Prayer Companion are documented in this file.

## [3.0.1] - 2026-10-20

### Fixed

- `ie-icci` prayer times silently fell back to the ISNA calculation. `https://islamireland.ie/api/timetable/` now returns the new ICCI website's HTML page instead of JSON.

### Changed

- `ie-icci` times now come from ICCI's own perpetual timetable, bundled in `custom_components/muslim_prayer_companion/data/icci_timetable.json` (from the [2 August 2022 Wayback Machine snapshot](https://web.archive.org/web/20220802110619id_/https://islamireland.ie/api/timetable/)). The `ie-icci` prayer times no longer make any network request.
- DST correction: the timetable changes clocks on 1 April and 1 November. Days where its Maghrib is more than 30 minutes off Home Assistant's local sunset are shifted by one hour, e.g. 30 Mar 2027 and 25–31 Oct 2026.
- `ie-icci` Midnight is now the midpoint between Maghrib and the next day's sunrise from the same timetable, instead of the ISNA calculation.
- If the bundled timetable is missing or corrupt, one warning is logged and `ie-icci` falls back to the ISNA calculation.
- `manifest.json` version is now in step with the release (the 3.0.0 release still said 2.2.0).
