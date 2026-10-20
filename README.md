# Muslim Prayer Companion

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![Downloads][downloads-shield]][downloads]

Muslim Prayer Companion is a Home Assistant Community Store (HACS) integration for prayer times, Iqamah times, Friday prayers, the Hijri calendar and Islamic companion features. Times come either from a calculation for any location in the world (23 methods, fully offline) or from an Irish mosque's own published timetable. Several locations and mosques can be set up side by side.

---

## Table of Contents

- [Features](#features)
- [Supported sources](#supported-sources)
- [Installation](#installation)
- [Configuration](#configuration)
- [Settings](#settings)
- [Friday prayers](#friday-prayers)
- [Iqamah times](#iqamah-times)
- [Hijri date and Imsak](#hijri-date-and-imsak)
- [Data sources, fallback and Repairs](#data-sources-fallback-and-repairs)
- [Sensors reference](#sensors-reference)
- [Events](#events)
- [Action: get_prayer_times](#action-get_prayer_times)
- [Upgrading from 3.0.x](#upgrading-from-30x)
- [Add your mosque](#add-your-mosque)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Features

- **Prayer times for any location**, calculated offline with 23 conventions (ISNA, MWL, Umm al-Qura, Egypt, Karachi, Moonsighting Committee, Diyanet, JAKIM and more).
- **Irish mosque timetables**: Islamic Cultural Centre of Ireland (ICCI), Muslim Community North Dublin (MCND), Hansfield Islamic Cultural Centre (HICC), South Dublin Islamic Centre (SDIC) and the Muslim Association of Ireland in Tallaght (MAI), read from each mosque's own published source.
- **Friday prayers**: track the Jumu'ah times of several mosques at once, published automatically where the mosque provides them or entered by hand, with a device and two sensors per mosque.
- **Iqamah times**: fixed offsets, the times published by the mosque, a custom JSON API, or off.
- **Hijri calendar**: offline conversion, adjustable by up to two days for local moon sighting, with the option to change the Hijri day at Maghrib.
- **Ramadan and special dates**: Ramadan day, days until Ramadan, Imsak, Iftar, special nights, upcoming Islamic event.
- **Live countdown**: next prayer, minutes to go and the current prayer period, recomputed every minute without any network traffic.
- **Events and an action** for automations: an event at every prayer, Iqamah, Imsak and Jumu'ah time, and `get_prayer_times` for timetables of up to 366 days.
- **Never silent, never unavailable**: if a mosque source fails, calculated times take over, the `source` attribute says so and a Repairs issue is opened until the source recovers.
- **Multiple entries**, each with its own device, settings and sensors. Entity IDs are unchanged since version 2.x.
- **English and Arabic** user interface, including entity names.
- **Diagnostics** download from the entry page (coordinates redacted).

### Platforms

| Platform | Description                                                                          |
| -------- | ------------------------------------------------------------------------------------ |
| `sensor` | Prayer times, Iqamah, Friday prayers, Hijri date, countdown, Qibla and special dates |

---

## Supported sources

### Irish mosques

| Method    | Mosque                                         | Source                                                                                                                                                                                                                                         | Credit                                                        |
| --------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `ie-icci` | Islamic Cultural Centre of Ireland, Clonskeagh | ICCI's perpetual timetable, bundled with the integration from the [Wayback Machine snapshot of 2 August 2022](https://web.archive.org/web/20220802110619id_/https://islamireland.ie/api/timetable/) of the former JSON API. No network needed. | [Islamic Cultural Centre of Ireland](https://islamireland.ie) |
| `ie-mcnd` | Muslim Community North Dublin                  | Daily Prayer Time WordPress plugin JSON API (prayer, Iqamah and Jumu'ah times)                                                                                                                                                                 | [Muslim Community North Dublin](https://mcnd.ie)              |
| `ie-hicc` | Hansfield Islamic Cultural Centre              | Daily Prayer Time WordPress plugin JSON API (prayer, Iqamah and Jumu'ah times)                                                                                                                                                                 | [Hansfield Islamic Cultural Centre](https://hicc.ie)          |
| `ie-sdic` | South Dublin Islamic Centre                    | Daily Prayer Time WordPress plugin JSON API (prayer, Iqamah and Jumu'ah times)                                                                                                                                                                 | [South Dublin Islamic Centre](https://sdic.ie)                |
| `ie-mai`  | Muslim Association of Ireland, Tallaght        | Daily times read from the public website (today only; Jumu'ah times are entered manually)                                                                                                                                                      | [Muslim Association of Ireland](https://maionline.ie)         |

All mosque data remains the property of the respective mosques. The mosque list lives in `custom_components/muslim_prayer_companion/data/mosques.json`; see [Add your mosque](#add-your-mosque).

### Calculation methods

Calculations use [prayer-times-calculator-offline](https://pypi.org/project/prayer-times-calculator-offline/), the same library as Home Assistant's core Islamic Prayer Times integration. Nothing is fetched from the internet.

| Method         | Convention                                    |
| -------------- | --------------------------------------------- |
| `isna`         | Islamic Society of North America (default)    |
| `mwl`          | Muslim World League                           |
| `makkah`       | Umm al-Qura University, Makkah                |
| `egypt`        | Egyptian General Authority of Survey          |
| `karachi`      | University of Islamic Sciences, Karachi       |
| `tehran`       | Institute of Geophysics, University of Tehran |
| `jafari`       | Shia Ithna-Ashari (Jafari)                    |
| `gulf`         | Gulf Region                                   |
| `kuwait`       | Kuwait                                        |
| `qatar`        | Qatar                                         |
| `singapore`    | Majlis Ugama Islam Singapura                  |
| `france`       | Union des Organisations Islamiques de France  |
| `turkey`       | Diyanet İşleri Başkanlığı, Turkey             |
| `russia`       | Spiritual Administration of Muslims of Russia |
| `moonsighting` | Moonsighting Committee Worldwide              |
| `dubai`        | Dubai                                         |
| `jakim`        | JAKIM, Malaysia                               |
| `tunisia`      | Tunisia                                       |
| `algeria`      | Algeria                                       |
| `kemenag`      | Kementerian Agama, Indonesia                  |
| `morocco`      | Morocco                                       |
| `portugal`     | Comunidade Islâmica de Lisboa, Portugal       |
| `jordan`       | Jordan                                        |

---

## Installation

### Prerequisites

- [Home Assistant](https://www.home-assistant.io/) 2025.2.4 or newer
- [HACS](https://hacs.xyz/) (for the HACS route)

### With HACS

1. Open HACS in Home Assistant.
2. Click the three dots (⋮) → **Custom repositories**.
3. Add `https://github.com/amaharek/muslim_prayer_companion` with category **Integration**.
4. Search for **Muslim Prayer Companion**, click **Download**.
5. Restart Home Assistant.

### Manually

1. Download the `muslim_prayer_companion.zip` asset of the [latest release][releases].
2. Unpack it into `config/custom_components/muslim_prayer_companion/` so that `manifest.json` ends up in that folder.
3. Restart Home Assistant.

---

## Configuration

Go to **Settings → Devices & services → Add integration** and search for **Muslim Prayer Companion**. The setup has two or three steps:

1. **Prayer times source**: calculate from a location, or use an Irish mosque's published timetable.
2. **Irish mosque**: pick the mosque. The list is ordered by distance from your Home Assistant location and the nearest one is preselected. The optional name (default: the mosque's short name, for example `ICCI`) is used in entity names.
   **Location** (calculated source): pick the coordinates on the map (default: your Home Assistant location) and a name such as `Home`.
3. **Calculation method** (calculated source only).

Each entry gets a device named `Muslim Prayer Companion - <name>` with all of its sensors. One entry per mosque and one entry per location can exist; adding the same mosque twice is refused.

Entity IDs follow `sensor.muslim_prayer_companion_<name>_<sensor>`, for example `sensor.muslim_prayer_companion_icci_maghrib`.

---

## Settings

Open the entry under **Settings → Devices & services → Muslim Prayer Companion** and click **Configure**. The menu has five pages; every page saves on its own and reloads the entry.

| Page                     | What it sets                                                                                                                                                                      |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Calculation method**   | The convention used for calculated entries (not shown for mosque entries).                                                                                                        |
| **Iqamah times**         | Where Iqamah times come from (offsets, the mosque, a custom API, or disabled), the custom API URL and the per-prayer offsets in minutes.                                          |
| **Friday prayers**       | The list of mosques whose Jumu'ah times are tracked: add, edit or remove mosques.                                                                                                 |
| **Hijri date and Imsak** | Hijri adjustment (−2 to +2 days), whether the Hijri day changes at Maghrib, and how many minutes before Fajr the Imsak sensor is set.                                             |
| **Sensors and display**  | Which sensor groups exist (Iqamah, Hijri, countdown, Qibla, special dates, Friday), the countdown format (`Asr in 45 minutes`, `00:45` or `45`) and the prayer window in minutes. |

To change the mosque, the location or the source itself, use **Reconfigure** in the entry's three-dot menu. Your other settings are kept, and the entry's unique ID follows the new mosque or location.

The **prayer window** controls the _Current prayer period_ sensor: for that many minutes after a prayer starts the sensor shows the prayer itself (`Dhuhr`) instead of `Between Dhuhr and Asr`. Set it to 0 to disable.

---

## Friday prayers

The **Friday prayers** page keeps a list of mosques, up to ten per entry. Each mosque has:

- a **name** (shown as the device name),
- a **source**: _Entered manually_, or a registered mosque that publishes its Jumu'ah times (MCND, HICC, SDIC). Mosques that do not publish them (ICCI, MAI) can be chosen as presets but their times are entered by hand,
- a first and an optional second **Jumu'ah time** (`HH:MM`), used as the times for manual mosques and as a fallback when a published list is empty,
- an optional **label** per session, for example _Men only_ or _Arabic khutbah_.

An Irish mosque entry starts with its own mosque in the list. Each mosque in the list becomes a device with two timestamp sensors, **Jumu'ah 1** and **Jumu'ah 2**, pointing at the next Friday occurrence, so they are available every day of the week. Their attributes are `mosque_name`, `label`, `source` and `times_from` (`api` or `manual`).

Deleting a Friday mosque's device from the device page removes the mosque from the list. Renaming a mosque keeps its sensors: the entity IDs are derived from a slug that is fixed when the mosque is added.

The older `juma_time` sensor is kept as an alias: it shows the mosque's published first Jumu'ah, else the first mosque in the Friday list, else next Friday's Dhuhr.

---

## Iqamah times

| Method                              | Behaviour                                                                                                                                                                                           |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fixed offsets after each prayer** | Prayer start plus the configured minutes (defaults: Fajr 20, Dhuhr 15, Asr 15, Maghrib 10, Isha 15).                                                                                                |
| **Published by the mosque**         | The jamah times from the mosque's API (MCND, HICC, SDIC; the default for those mosques). Offsets fill any gaps.                                                                                     |
| **Custom JSON API**                 | A URL returning JSON such as `{"Fajr": "06:30", "Dhuhr": "13:30", ...}` (the `*_jamah` keys of the Daily Prayer Time plugin are also understood). The last good values are kept when the URL fails. |
| **Disabled**                        | No Iqamah sensors.                                                                                                                                                                                  |

Iqamah sensors keep showing today's Iqamah while it is still ahead, even after the prayer itself has started, and then move to the next day. Their `source` attribute is `offset`, `mosque` or `api`.

---

## Hijri date and Imsak

Hijri dates are converted offline with [hijridate](https://pypi.org/project/hijridate/) (Umm al-Qura calendar). Two settings adapt it to local practice:

- **Hijri date adjustment** shifts the date by −2 to +2 days to follow your community's moon-sighting announcements. Ramadan, special nights and the upcoming event follow the adjusted date.
- **Hijri day changes at Maghrib** advances the Hijri date (and everything derived from it) at Maghrib instead of midnight.

**Imsak** is Fajr minus a configurable number of minutes (default 10). **Iftar** equals Maghrib and is only set during Ramadan.

---

## Data sources, fallback and Repairs

Every prayer-time sensor carries a `source` attribute:

| `source`                           | Meaning                                                                           |
| ---------------------------------- | --------------------------------------------------------------------------------- |
| `icci-timetable`                   | Bundled ICCI perpetual timetable                                                  |
| `mcnd-api`, `hicc-api`, `sdic-api` | The mosque's Daily Prayer Time API                                                |
| `mai-website`                      | Today's times read from maionline.ie                                              |
| `calculated:<method>`              | Calculated for the entry's coordinates, e.g. `calculated:isna`                    |
| `calculated-fallback:isna`         | A mosque source failed; ISNA times for the mosque's coordinates are shown instead |

When a mosque source cannot be read (dead endpoint, HTML instead of JSON, timeout, changed page layout), the entry does not go unavailable: it falls back to calculated ISNA times for the same coordinates, logs one warning, and opens a **Repairs** issue (**Settings → System → Repairs**) naming the mosque, the URL and the error. The source is tried again every hour; when it works, the issue closes itself and the `source` attribute changes back. If even the calculation fails, today's last good times are kept, and a new entry retries with increasing delays.

Mosque sources are also checked once a week by a GitHub Action in this repository, which opens an issue when one of them breaks.

### ICCI timetable details

The ICCI table is perpetual (366 days, no year) and uses summer time for all dates from 1 April to 31 October and GMT otherwise, whatever the real clock change date is. The integration converts each day with that fixed rule, so the few days each year between the real DST change and the table's switch are shifted by one hour. Midnight is the midpoint of Maghrib and the next day's sunrise. The bundled file is verified against a checksum in the tests and can be rebuilt with `scripts/build_icci_timetable.py`.

---

## Sensors reference

Unique IDs are `{key}_{entry_id}` and have not changed since version 2.x, so history, dashboards and automations survive upgrades. Timestamp sensors hold ISO 8601 UTC values, which Home Assistant shows in your local time. Boolean sensors are strings `"true"`/`"false"`.

### Prayer times (always created)

| Key                     | Entity name           | Class       | Description                                                                             |
| ----------------------- | --------------------- | ----------- | --------------------------------------------------------------------------------------- |
| `Fajr`                  | Fajr                  | `timestamp` | Next Fajr (today's until it passes, then tomorrow's)                                    |
| `Sunrise`               | Sunrise               | `timestamp` | Next sunrise                                                                            |
| `Dhuhr`                 | Dhuhr                 | `timestamp` | Next Dhuhr                                                                              |
| `Asr`                   | Asr                   | `timestamp` | Next Asr                                                                                |
| `Maghrib`               | Maghrib               | `timestamp` | Next Maghrib                                                                            |
| `Isha`                  | Isha                  | `timestamp` | Next Isha                                                                               |
| `Midnight`              | Midnight              | `timestamp` | Islamic midnight (midpoint of Maghrib and the next sunrise)                             |
| `next_prayer`           | Next prayer           | `timestamp` | Time of the next of the five prayers; attribute `prayer` holds its name                 |
| `current_prayer_period` | Current prayer period | text        | `Before Fajr`, `<Prayer>` during the prayer window, `Between <X> and <Y>`, `After Isha` |
| `location_name`         | Location              | text        | The entry's name                                                                        |

Attributes: `source` on every timestamp above.

### Countdown

| Key                     | Entity name            | Description                                           |
| ----------------------- | ---------------------- | ----------------------------------------------------- |
| `next_prayer_countdown` | Next prayer countdown  | `Asr in 45 minutes`, `00:45` or `45` (per the format) |
| `next_prayer_minutes`   | Minutes to next prayer | Whole minutes, unit `min`                             |

### Hijri date

| Key                        | Entity name           | Example                                           |
| -------------------------- | --------------------- | ------------------------------------------------- |
| `hijri_date`               | Hijri date            | `09-05-1448`                                      |
| `hijri_day`                | Hijri day             | `9`                                               |
| `hijri_month_num`          | Hijri month number    | `5`                                               |
| `hijri_month_readable`     | Hijri month           | `Jumada al-Awwal`                                 |
| `hijri_year`               | Hijri year            | `1448`                                            |
| `hijri_date_readable`      | Hijri date (readable) | `9-Jumada al-Awwal-1448` (attribute `is_ramadan`) |
| `hijri_day_month_readable` | Hijri day and month   | `9-Jumada al-Awwal`                               |

### Iqamah

| Key              | Entity name    | Class       |
| ---------------- | -------------- | ----------- |
| `iqamah_Fajr`    | Iqamah Fajr    | `timestamp` |
| `iqamah_Dhuhr`   | Iqamah Dhuhr   | `timestamp` |
| `iqamah_Asr`     | Iqamah Asr     | `timestamp` |
| `iqamah_Maghrib` | Iqamah Maghrib | `timestamp` |
| `iqamah_Isha`    | Iqamah Isha    | `timestamp` |

Attribute: `source` (`offset`, `mosque` or `api`).

### Qibla

| Key               | Entity name     | Description                                                              |
| ----------------- | --------------- | ------------------------------------------------------------------------ |
| `qibla_direction` | Qibla direction | Bearing to Makkah in degrees; attribute `compass_direction` (e.g. `ESE`) |

### Special dates

| Key                      | Entity name            | Class        | Description                                                                                          |
| ------------------------ | ---------------------- | ------------ | ---------------------------------------------------------------------------------------------------- |
| `is_ramadan`             | Ramadan                | text         | `true` during Ramadan                                                                                |
| `is_friday`              | Friday                 | text         | `true` on Fridays (local date)                                                                       |
| `special_night`          | Special night          | text         | Laylatul Qadr nights, night before Eid al-Fitr, Arafah, Bara'ah, Mi'raj, Ashura; `unknown` otherwise |
| `ramadan_day`            | Ramadan day            | number       | 1–30 during Ramadan, `unknown` otherwise                                                             |
| `days_until_ramadan`     | Days until Ramadan     | number (`d`) | Days to the next 1 Ramadan, `unknown` during Ramadan                                                 |
| `upcoming_islamic_event` | Upcoming Islamic event | text         | Next event name; attributes `date` and `days_until`                                                  |
| `imsak`                  | Imsak                  | `timestamp`  | Fajr minus the configured minutes                                                                    |
| `iftar`                  | Iftar                  | `timestamp`  | Maghrib, during Ramadan only                                                                         |

### Friday

| Key                      | Entity name | Class       | Description                                                                                        |
| ------------------------ | ----------- | ----------- | -------------------------------------------------------------------------------------------------- |
| `juma_time`              | Jumu'ah     | `timestamp` | Compatibility alias: next Friday's first Jumu'ah (published, else first Friday mosque, else Dhuhr) |
| `friday_<slug>_jumuah_1` | Jumu'ah 1   | `timestamp` | One per Friday mosque, under the mosque's own device                                               |
| `friday_<slug>_jumuah_2` | Jumu'ah 2   | `timestamp` | Second session; `unknown` when the mosque has one                                                  |

Friday sensor attributes: `mosque_name`, `label`, `source`, `times_from`.

---

## Events

The integration fires `muslim_prayer_companion_event` on the Home Assistant event bus at the exact minute of every prayer time, Iqamah time, Imsak and Jumu'ah time.

| Field                                | Present for        | Value                                                                                                                |
| ------------------------------------ | ------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `type`                               | all                | `prayer`, `iqamah`, `imsak` or `jumuah`                                                                              |
| `entry_id`                           | all                | The config entry                                                                                                     |
| `location_name`                      | all                | The entry's name                                                                                                     |
| `time`                               | all                | The instant, ISO 8601 UTC                                                                                            |
| `prayer`                             | `prayer`, `iqamah` | `Fajr`, `Sunrise`, `Dhuhr`, `Asr`, `Maghrib`, `Isha` or `Midnight` (`prayer` type); the five prayers (`iqamah` type) |
| `mosque`, `slug`, `session`, `label` | `jumuah`           | Friday mosque name and slug, session `1` or `2`, the session's label                                                 |

### Play the adhan at each prayer

```yaml
automation:
  - alias: "Play adhan"
    triggers:
      - trigger: event
        event_type: muslim_prayer_companion_event
        event_data:
          type: prayer
    conditions:
      - condition: template
        value_template: "{{ trigger.event.data.prayer in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'] }}"
    actions:
      - action: media_player.play_media
        target:
          entity_id: media_player.living_room_speaker
        data:
          media_content_id: "http://your-server/adhan.mp3"
          media_content_type: music
```

### Notify 10 minutes before the next prayer

```yaml
automation:
  - alias: "Prayer in 10 minutes"
    triggers:
      - trigger: time
        at:
          entity_id: sensor.muslim_prayer_companion_home_next_prayer
          offset: "-00:10:00"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "Prayer reminder"
          message: >-
            {{ state_attr('sensor.muslim_prayer_companion_home_next_prayer', 'prayer') }}
            in 10 minutes
```

### Friday reminder

```yaml
automation:
  - alias: "Jumu'ah reminder"
    triggers:
      - trigger: event
        event_type: muslim_prayer_companion_event
        event_data:
          type: jumuah
          session: 1
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "Jumu'ah"
          message: >-
            Jumu'ah is starting at {{ trigger.event.data.mosque }}
            {% if trigger.event.data.label %}({{ trigger.event.data.label }}){% endif %}
```

For a reminder before the Jumu'ah, use a time trigger with a negative offset on the mosque's **Jumu'ah 1** sensor, as in the previous example.

---

## Action: get_prayer_times

`muslim_prayer_companion.get_prayer_times` returns the prayer times of one or more days, for example to build a Ramadan timetable card.

| Field             | Required | Description                                              |
| ----------------- | -------- | -------------------------------------------------------- |
| `config_entry_id` | no       | The entry to use; defaults to the first configured entry |
| `date`            | no       | First day (`YYYY-MM-DD`); defaults to today              |
| `days`            | no       | Number of consecutive days, 1–366 (default 1)            |

Calculated entries and ICCI can answer for any date. The MCND, HICC, SDIC and MAI sources only know today and tomorrow and raise an error for later dates.

```yaml
action: muslim_prayer_companion.get_prayer_times
data:
  config_entry_id: 01ABCDEF0123456789ABCDEFGHIJKL
  date: "2026-02-18"
  days: 30
response_variable: ramadan
```

Response:

```yaml
location_name: ICCI
provider: Islamic Cultural Centre of Ireland
days:
  - date: "2026-02-18"
    Fajr: "2026-02-18T05:55:00+00:00"
    Sunrise: "2026-02-18T07:36:00+00:00"
    Dhuhr: "2026-02-18T12:41:00+00:00"
    Asr: "2026-02-18T15:09:00+00:00"
    Maghrib: "2026-02-18T17:42:00+00:00"
    Isha: "2026-02-18T19:18:00+00:00"
    Midnight: "2026-02-19T00:38:00+00:00"
    Sunset: "2026-02-18T17:42:00+00:00"
    source: icci-timetable
  - ...
```

---

## Upgrading from 3.0.x

Config entries are migrated automatically to version 3, and entity unique IDs are unchanged, so dashboards and automations keep working. Two behaviour changes are worth knowing:

- **The calculation method you chose is now applied.** In 3.0.x the method selected in the UI was ignored and every entry effectively showed ICCI times. 4.0.0 honours the stored method (reading options first, as 3.0.x did), so prayer times may change after upgrading. Check the entry's **Configure** menu or **Reconfigure** it.
- The old _Enable Hijri sensors_ and _Enable countdown sensors_ toggles were stored but never applied; they now disable those sensor groups.

Other visible changes: `juma_time` is available every day (not only on Fridays), `special_night` is `unknown` instead of empty when there is nothing special, and _Current prayer period_ shows the prayer's own name during the prayer window.

---

## Add your mosque

Mosques are data, not code: one record in `custom_components/muslim_prayer_companion/data/mosques.json` plus a label in the translation files adds a mosque that publishes its times with the Daily Prayer Time WordPress plugin. Other formats need a small parser. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Development

```bash
git clone https://github.com/amaharek/muslim_prayer_companion.git
cd muslim_prayer_companion

python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest -q --cov                       # tests with coverage
ruff check . && ruff format .         # lint and format
pre-commit run --all-files            # every hook

python -I scripts/build_icci_timetable.py --check     # verify the bundled ICCI table
python -I scripts/build_icci_timetable.py --download  # rebuild it from the Wayback snapshot
python scripts/check_mosques.py                       # fetch and parse every mosque source
```

Continuous integration runs the tests against Home Assistant 2025.2.4 (the minimum) and the latest release, ruff and pre-commit, hassfest and HACS validation. A weekly workflow runs `scripts/check_mosques.py` and opens an issue when a mosque source breaks.

### Project structure

```
custom_components/muslim_prayer_companion/
├── __init__.py            # Setup, migration, device removal, get_prayer_times action
├── config_flow.py         # Setup, reconfigure and options menu
├── coordinator.py         # Fetch, fallback + Repairs, per-minute tick, events
├── sensor.py              # Sensor platform (groups, Friday devices, cleanup)
├── diagnostics.py
├── services.yaml
├── data/
│   ├── mosques.json       # Mosque registry
│   └── icci_timetable.json
├── api_providers/
│   ├── base.py            # Data models, provider interface
│   ├── calculated.py      # prayer-times-calculator-offline
│   ├── ireland.py         # Irish mosques (dispatch by source type)
│   ├── icci_timetable.py  # Bundled ICCI table
│   ├── dpt.py             # Daily Prayer Time plugin parser
│   ├── mai.py             # maionline.ie homepage parser
│   └── http.py
├── helpers/
│   ├── derived.py         # Pure builder of the sensor data
│   ├── friday.py          # Friday prayers
│   ├── iqamah.py
│   ├── hijri.py / special_dates.py / qibla.py
│   ├── registry.py        # mosques.json loader
│   └── settings.py        # Typed options
└── translations/          # en, ar (strings.json mirrors en)
```

---

## Troubleshooting

- **A Repairs issue says prayer times are calculated, not from the mosque.** The mosque's source could not be read; the issue text shows the URL and the error. Times keep coming from the ISNA calculation until the source recovers, after which the issue closes itself. If it stays open for days, the source has probably changed: please open an issue here.
- **Prayer times look wrong.** Check the `source` attribute of a prayer-time sensor, the calculation method (**Configure → Calculation method**) and your Home Assistant time zone.
- **Entities are missing.** The sensor group may be disabled under **Configure → Sensors and display**.
- **Debug logging:**

  ```yaml
  logger:
    default: warning
    logs:
      custom_components.muslim_prayer_companion: debug
  ```

- **Diagnostics:** on the entry page, choose **Download diagnostics** (coordinates are redacted) and attach the file to your issue.
- **Help:** [GitHub Issues](https://github.com/amaharek/muslim_prayer_companion/issues).

---

## License

Apache 2.0, see [LICENSE](LICENSE).

---

## Acknowledgments

- The Islamic Cultural Centre of Ireland, Muslim Community North Dublin, Hansfield Islamic Cultural Centre, South Dublin Islamic Centre and the Muslim Association of Ireland for publishing their prayer times.
- [prayer-times-calculator-offline](https://pypi.org/project/prayer-times-calculator-offline/) and [hijridate](https://pypi.org/project/hijridate/).
- The Home Assistant community.

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[commits]: https://github.com/amaharek/muslim_prayer_companion/commits/main
[license-shield]: https://img.shields.io/github/license/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[releases]: https://github.com/amaharek/muslim_prayer_companion/releases
[downloads-shield]: https://img.shields.io/github/downloads/amaharek/muslim_prayer_companion/total.svg?style=for-the-badge
[downloads]: https://github.com/amaharek/muslim_prayer_companion/releases
