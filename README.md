# Muslim Prayer Companion

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![Downloads][downloads-shield]][downloads]

Muslim Prayer Companion is a Home Assistant Community Store (HACS) integration designed to provide accurate prayer times based on your location. This integration seamlessly integrates daily prayer schedules, including Iqamah and Jummah times, into your smart home, ensuring timely reminders and notifications for all five daily prayers.

## Features

- Accurate prayer times tailored to your location.
- Integration with Home Assistant for automated reminders and notifications.
- Support for Iqamah and Jummah times.
- Hijri calendar information, including Hijri date, month, and year.
- Configurable calculation methods for prayer times.
- Sensors for prayer times, Iqamah times, Hijri date, and the next prayer.
- Easy configuration through the Home Assistant UI.

## Platforms

This integration sets up the following platform:

| Platform | Description                                                                   |
| -------- | ----------------------------------------------------------------------------- |
| `sensor` | Displays prayer times, Iqamah times, Hijri date, and next prayer information. |

## Installation

### Prerequisites

- Ensure you have [Home Assistant](https://www.home-assistant.io/) installed.
- Install [HACS](https://hacs.xyz/) if not already installed.

### Steps

1. **Open HACS in your Home Assistant instance.**
   - Navigate to the HACS section from the sidebar.

2. **Add the Muslim Prayer Companion repository as a custom repository:**
   - Click on the three dots (⋮) in the top right corner and select **Custom repositories**.
   - In the dialog that appears:
     - Paste the URL of the Muslim Prayer Companion repository: `https://github.com/amaharek/muslim_prayer_companion`.
     - Select **Integration** as the category.
     - Click the **Add** button.

3. **Install the integration:**
   - After adding the custom repository, search for **Muslim Prayer Companion** in the HACS integrations section.
   - Click on the integration and then click the **Download** button to install it.

4. **Restart Home Assistant:**
   - After installation, it's recommended to restart Home Assistant to ensure all changes take effect.

## Configuration

1. **Add the integration:**
   - Navigate to **Settings > Devices & Services > Add Integration**.
   - Search for **Muslim Prayer Companion** and select it.

2. **Configure the integration:**
   - Follow the on-screen instructions to configure the integration, including selecting your preferred calculation method.

### Configuring the Calculation Method

The integration supports multiple calculation methods for prayer times. During setup, you can select one of the following methods:

| Calculation Method | Description                                                   |
| ------------------ | ------------------------------------------------------------- |
| `isna`             | Islamic Society of North America (default).                   |
| `mwl`              | Muslim World League.                                          |
| `karachi`          | University of Islamic Sciences, Karachi.                      |
| `makkah`           | Umm al-Qura University, Makkah.                               |
| `egypt`            | Egyptian General Authority of Survey.                         |
| `tehran`           | Institute of Geophysics, University of Tehran.                |
| `ie-icci`          | Islamic Cultural Centre of Ireland (recommended for Ireland). |
| `ie-mcnd`          | Muslim Community North Dublin.                                |
| `ie-hicc`          | Hansfield Islamic Cultural Centre.                            |

#### ICCI prayer times

The `ie-icci` times come from the Islamic Cultural Centre of Ireland's own prayer timetable, credited to the [Islamic Cultural Centre of Ireland](https://islamireland.ie). ICCI no longer publishes the timetable as JSON, so the integration bundles a copy of its perpetual timetable, taken from this [Wayback Machine snapshot](https://web.archive.org/web/20220802110619id_/https://islamireland.ie/api/timetable/) (2 August 2022). The times are worked out offline and need no network access. The timetable changes clocks on 1 April and 1 November, so on the days between the real Irish DST change and those dates the integration shifts all times by one hour, checked against Home Assistant's local sunset.

You can update the calculation method later by editing the integration's options in **Settings > Devices & Services > Muslim Prayer Companion > Configure**.

## Sensors

The integration creates the following sensors:

### Prayer Times

| Sensor ID         | Description         | Example Value          |
| ----------------- | ------------------- | ---------------------- |
| `sensor.fajr`     | Fajr prayer time    | `2024-02-10T05:00:00Z` |
| `sensor.sunrise`  | Sunrise time        | `2024-02-10T06:30:00Z` |
| `sensor.dhuhr`    | Dhuhr prayer time   | `2024-02-10T12:00:00Z` |
| `sensor.asr`      | Asr prayer time     | `2024-02-10T15:30:00Z` |
| `sensor.maghrib`  | Maghrib prayer time | `2024-02-10T18:00:00Z` |
| `sensor.isha`     | Isha prayer time    | `2024-02-10T19:30:00Z` |
| `sensor.midnight` | Midnight time       | `2024-02-10T00:00:00Z` |

### Iqamah Times

| Sensor ID               | Description             | Example Value          |
| ----------------------- | ----------------------- | ---------------------- |
| `sensor.iqamah_fajr`    | Iqamah time for Fajr    | `2024-02-10T05:20:00Z` |
| `sensor.iqamah_dhuhr`   | Iqamah time for Dhuhr   | `2024-02-10T12:15:00Z` |
| `sensor.iqamah_asr`     | Iqamah time for Asr     | `2024-02-10T15:45:00Z` |
| `sensor.iqamah_maghrib` | Iqamah time for Maghrib | `2024-02-10T18:10:00Z` |
| `sensor.iqamah_isha`    | Iqamah time for Isha    | `2024-02-10T19:45:00Z` |

### Hijri Date

| Sensor ID                         | Description                            | Example Value     |
| --------------------------------- | -------------------------------------- | ----------------- |
| `sensor.hijri_date`               | Hijri date (DD-MM-YYYY)                | `10-09-1444`      |
| `sensor.hijri_day`                | Hijri day                              | `10`              |
| `sensor.hijri_month_num`          | Hijri month number                     | `9`               |
| `sensor.hijri_month_readable`     | Hijri month name                       | `Ramadan`         |
| `sensor.hijri_year`               | Hijri year                             | `1444`            |
| `sensor.hijri_date_readable`      | Hijri date in readable format          | `10-Ramadan-1444` |
| `sensor.hijri_day_month_readable` | Hijri day and month in readable format | `10-Ramadan`      |

### Next Prayer

| Sensor ID                 | Description             | Example Value          |
| ------------------------- | ----------------------- | ---------------------- |
| `sensor.next_prayer`      | Time of the next prayer | `2024-02-10T12:00:00Z` |
| `sensor.next_prayer_name` | Name of the next prayer | `Dhuhr`                |

## Sample Sensor Data Format

Here is an example of the sensor data in JSON format:

```json
{
  "fajr": "2024-02-10T05:00:00Z",
  "sunrise": "2024-02-10T06:30:00Z",
  "dhuhr": "2024-02-10T12:00:00Z",
  "asr": "2024-02-10T15:30:00Z",
  "maghrib": "2024-02-10T18:00:00Z",
  "isha": "2024-02-10T19:30:00Z",
  "midnight": "2024-02-10T00:00:00Z",
  "iqamah_fajr": "2024-02-10T05:20:00Z",
  "iqamah_dhuhr": "2024-02-10T12:15:00Z",
  "iqamah_asr": "2024-02-10T15:45:00Z",
  "iqamah_maghrib": "2024-02-10T18:10:00Z",
  "iqamah_isha": "2024-02-10T19:45:00Z",
  "hijri_date": "10-09-1444",
  "hijri_day": "10",
  "hijri_month_num": 9,
  "hijri_month_readable": "Ramadan",
  "hijri_year": "1444",
  "hijri_date_readable": "10-Ramadan-1444",
  "hijri_day_month_readable": "10-Ramadan",
  "next_prayer": "2024-02-10T12:00:00Z",
  "next_prayer_name": "Dhuhr"
}
```

## Testing and Development

To run tests and ensure code quality, use the following commands:

```bash
poetry run pytest --cov custom_components/ tests/
poetry run pre-commit run --all-files
```

[muslim_prayer_companion]: https://github.com/amaharek/muslim_prayer_companion
[commits-shield]: https://img.shields.io/github/commit-activity/y/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[commits]: https://github.com/amaharek/muslim_prayer_companion/commits/{branch}
[license-shield]: https://img.shields.io/github/license/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/amaharek/muslim_prayer_companion.svg?style=for-the-badge
[releases]: https://github.com/amaharek/muslim_prayer_companion/releases
[downloads-shield]: https://img.shields.io/github/downloads/amaharek/muslim_prayer_companion/total.svg?style=for-the-badge
[downloads]: https://github.com/amaharek/muslim_prayer_companion/releases
