"""
Muslim Prayer Companion Coordinator
"""

from __future__ import annotations

import calendar
import json
import logging
from datetime import date, datetime, time, timedelta
from functools import cache
from pathlib import Path

import async_timeout
import homeassistant.util.dt as dt_util
import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNSET
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from prayer_times_calculator import PrayerTimesCalculator, exceptions
from requests.exceptions import ConnectionError as ConnError

from .const import (
    CONF_CALC_METHOD,
    CONF_IQAMAH_METHOD,
    CONF_IQAMAH_OFFSETS,
    DEFAULT_CALC_METHOD,
    DEFAULT_IQAMAH_METHOD,
    DEFAULT_IQAMAH_OFFSETS,
    DOMAIN,
    LOGGER,
)

# --- Utility functions ---


def format_time(time_list: list[int], offset: int = 0) -> str:
    """
    Convert a list of hour/minutes of a prayer to time in format HH:MM.

    Args:
        time_list (list): [hour, minute]
        offset (int): Hour offset correction

    Returns:
        str: Time in format HH:MM
    """
    hour = time_list[0] + offset
    return f"{str(hour % 24).zfill(2)}:{str(time_list[1]).zfill(2)}"


def get_time_list(str_time: str) -> list[int]:
    """
    Convert time string in format HH:MM to time list [hour, minute].

    Args:
        str_time (str): Time string in format HH:MM

    Returns:
        list: [hour, minute]
    """
    return [int(num) for num in str_time.split(":")]


def get_standard_sunset_midnight(
    latitude: float, longitude: float, calculation_method: str
):
    """
    Return Maghrib time & Midnight time for given latitude, longitude & calculation method.

    Args:
        latitude (float): Latitude
        longitude (float): Longitude
        calculation_method (str): Calculation method

    Returns:
        tuple: Maghrib time, Midnight time, Full Standard Prayers
    """
    midnight = "00:00"
    maghrib = ""
    std_prayers = {}
    try:
        calc = PrayerTimesCalculator(
            latitude=latitude,
            longitude=longitude,
            calculation_method="isna",
            date=str(date.today()),
        )
        std_prayers = calc.fetch_prayer_times()
        midnight = std_prayers.get("Midnight", "00:00")
        maghrib = std_prayers.get("Maghrib", "")
    except Exception as e:
        LOGGER.info(f"Failed to extract midnight/maghrib from ISNA calculation: {e}")
    return maghrib, midnight, std_prayers


def get_json_response(url: str):
    """
    Return JSON response from HTTP request.

    Args:
        url (str): URL to fetch JSON from

    Returns:
        dict: JSON response
    """
    try:
        resp = requests.get(url=url, timeout=10)
        if resp.status_code == requests.codes.ok:
            return resp.json()
        else:
            LOGGER.debug(f"{url} : request failed with status code {resp.status_code}")
    except Exception as e:
        LOGGER.info(f"{url} : request exception raised, got error: {e}")
    return None


def get_hour_offset_fix(non_standard_str: str, standard_str: str) -> int:
    """
    Compare the prayer between the standard and non-standard one, and give the fix offset for the broken week at the start and end of the DST.

    Args:
        non_standard_str (str): Non-standard time in format HH:MM
        standard_str (str): Standard time in format HH:MM

    Returns:
        int: Hour offset
    """
    try:
        non_standard = datetime.strptime(non_standard_str, "%H:%M")
        standard = datetime.strptime(standard_str, "%H:%M")
    except Exception as e:
        LOGGER.info(f"Failed to parse time expecting HH:MM format: {e}")
        return 0

    delta = (
        (non_standard - standard).seconds
        if non_standard > standard
        else (standard - non_standard).seconds
    )
    if delta > 900:
        return -1 if non_standard > standard else 1
    return 0


def get_prayers_by_wp_plugin(url: str, name: str, standard_maghrib: str, midnight: str):
    """
    Get the prayers from a WordPress site with the Daily Prayer Time plugin.

    Args:
        url (str): URL to fetch prayers from
        name (str): Name of the calculation method
        standard_maghrib (str): Standard Maghrib time
        midnight (str): Midnight time

    Returns:
        dict: Prayer times information
    """
    json_resp = get_json_response(url)
    if json_resp:
        try:
            wp_prayers = json_resp[0]
            hr_offset = get_hour_offset_fix(
                wp_prayers["maghrib_begins"][0:5], standard_maghrib
            )
            prayer_times_info = {
                "Fajr": format_time(
                    get_time_list(wp_prayers["fajr_begins"][0:5]), hr_offset
                ),
                "Sunrise": format_time(
                    get_time_list(wp_prayers["sunrise"][0:5]), hr_offset
                ),
                "Dhuhr": format_time(
                    get_time_list(wp_prayers["zuhr_begins"][0:5]), hr_offset
                ),
                "Asr": format_time(
                    get_time_list(wp_prayers["asr_mithl_1"][0:5]), hr_offset
                ),
                "Sunset": format_time(
                    get_time_list(wp_prayers["maghrib_begins"][0:5]), hr_offset
                ),
                "Maghrib": format_time(
                    get_time_list(wp_prayers["maghrib_begins"][0:5]), hr_offset
                ),
                "Isha": format_time(
                    get_time_list(wp_prayers["isha_begins"][0:5]), hr_offset
                ),
                "Imsak": format_time(
                    get_time_list(wp_prayers["maghrib_begins"][0:5]), hr_offset
                ),
                "Midnight": midnight,
            }
            return prayer_times_info
        except Exception as e:
            LOGGER.info(f"Failed to retrieve prayer from {name}, JSON parse error: {e}")
    return None


# --- ICCI timetable ---

ICCI_TIMETABLE_PATH = Path(__file__).parent / "data" / "icci_timetable.json"
ICCI_DST_THRESHOLD = timedelta(minutes=30)


def is_valid_icci_day(prayers: list[list[int]]) -> bool:
    """
    Check one timetable day: six [hour, minute] pairs.

    Args:
        prayers (list): [hour, minute] for fajr, shurooq, dhuhr, asr, maghrib, isha

    Returns:
        bool: True if the day is well formed
    """
    return len(prayers) == 6 and all(
        len(pair) == 2
        and all(isinstance(value, int) for value in pair)
        and 0 <= pair[0] < 24
        and 0 <= pair[1] < 60
        for pair in prayers
    )


@cache
def load_icci_timetable() -> dict[str, dict[str, list[list[int]]]] | None:
    """
    Load the bundled ICCI timetable, once per run.

    The timetable is keyed by month then day ("1".."12", "1".."31", with 29 Feb)
    and holds the six prayer times of each day in local Irish clock time.
    This reads a file: call it from executor code, never from the event loop.

    Returns:
        dict: The timetable, or None if the file is missing or corrupt
    """
    try:
        data = json.loads(ICCI_TIMETABLE_PATH.read_text(encoding="utf-8"))
        timetable = data["timetable"]
        for month in range(1, 13):
            # 2024 is a leap year, so 29 Feb must be present too.
            for day in range(1, calendar.monthrange(2024, month)[1] + 1):
                if not is_valid_icci_day(timetable[str(month)][str(day)]):
                    msg = f"invalid prayer times for {day}/{month}"
                    raise ValueError(msg)
    except (OSError, ValueError, KeyError, TypeError) as e:
        LOGGER.warning(
            "ICCI timetable %s is missing or corrupt (%s), "
            "falling back to the ISNA calculation",
            ICCI_TIMETABLE_PATH,
            e,
        )
        return None
    return timetable


def get_dst_hour_offset(
    table_maghrib: list[int], target_date: date, local_sunset: datetime
) -> int:
    """
    Give the hour fix for a timetable day on the wrong clock (summer time or GMT).

    The ICCI timetable changes clocks on 1 April and 1 November instead of the
    actual DST dates. Its Maghrib is always within minutes of sunset, so a gap
    of more than 30 minutes means the whole day is one hour off.

    Args:
        table_maghrib (list): Maghrib from the timetable, [hour, minute]
        target_date (date): Day the timetable entry is used for
        local_sunset (datetime): Sunset on that day, in local time

    Returns:
        int: Hour offset (-1, 0 or 1)
    """
    maghrib = datetime.combine(target_date, time(*table_maghrib))
    delta = maghrib - local_sunset.replace(tzinfo=None)
    if abs(delta) <= ICCI_DST_THRESHOLD:
        return 0
    return -1 if delta > timedelta(0) else 1


def get_local_datetime(day: date, time_list: list[int], offset: int = 0) -> datetime:
    """
    Combine a day and a timetable time into a local, timezone-aware datetime.

    Args:
        day (date): Day
        time_list (list): [hour, minute]
        offset (int): Hour offset correction

    Returns:
        datetime: Local time on that day
    """
    return datetime.combine(
        day,
        time((time_list[0] + offset) % 24, time_list[1]),
        tzinfo=dt_util.get_default_time_zone(),
    )


def get_midnight(maghrib: datetime, next_sunrise: datetime) -> str:
    """
    Return the midpoint between Maghrib and the next day's sunrise.

    The arithmetic is done in UTC, so a DST change during the night is counted.

    Args:
        maghrib (datetime): Maghrib, timezone-aware
        next_sunrise (datetime): Sunrise on the next day, timezone-aware

    Returns:
        str: Local time in format HH:MM, rounded down to the minute
    """
    start = dt_util.as_utc(maghrib)
    midnight = start + (dt_util.as_utc(next_sunrise) - start) / 2
    return dt_util.as_local(midnight).strftime("%H:%M")


# --- Coordinator Class ---


class MuslimPrayerCompanionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, any]]):
    """Muslim Prayer Companion Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        self.event_unsub: CALLBACK_TYPE | None = None
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=60),
        )

    @property
    def calc_method(self) -> str:
        """Return the calculation method."""
        return self.config_entry.options.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)

    @property
    def iqamah_method(self) -> str:
        """Return the iqamah method."""
        return self.config_entry.options.get(CONF_IQAMAH_METHOD, DEFAULT_IQAMAH_METHOD)

    def get_hijri_date(self) -> dict[str, str]:
        """Fetch Hijri date."""
        calc = PrayerTimesCalculator(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            calculation_method="isna",
            date=str(date.today()),
        )
        hijri_data = calc.fetch_prayer_times().get("date")
        hijri_date = hijri_data["hijri"]["date"]  # DD-MM-YYYY
        hijri_day = hijri_data["hijri"]["day"]
        hijri_month_num = hijri_data["hijri"]["month"]["number"]
        hijri_month_readable = hijri_data["hijri"]["month"]["en"]
        hijri_year = hijri_data["hijri"]["year"]
        hijri_day_month_readable = f"{hijri_day}-{hijri_month_readable}"
        hijri_date_readable = f"{hijri_day}-{hijri_month_readable}-{hijri_year}"

        return {
            "hijri_date": hijri_date,
            "hijri_day": hijri_day,
            "hijri_month_num": hijri_month_num,
            "hijri_month_readable": hijri_month_readable,
            "hijri_year": hijri_year,
            "hijri_date_readable": hijri_date_readable,
            "hijri_day_month_readable": hijri_day_month_readable,
        }

    def _get_prayer_times_standard(self, target_date: date) -> dict[str, str]:
        """Fetch prayer times for standard calculation methods on target_date."""
        calc = PrayerTimesCalculator(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            calculation_method="isna",
            date=str(target_date),
        )
        return calc.fetch_prayer_times()

    def _get_icci_hour_offset(self, prayers: list[list[int]], target_date: date) -> int:
        """Return the DST hour fix for an ICCI timetable day, using local sunset."""
        sunset = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, target_date)
        if sunset is not None:
            return get_dst_hour_offset(
                prayers[4], target_date, dt_util.as_local(sunset)
            )
        # No sunset at this location on that day: compare with ISNA instead.
        try:
            st_maghrib = self._get_prayer_times_standard(target_date)["Maghrib"]
        except Exception as e:
            LOGGER.info("Failed to get the ISNA Maghrib for the ICCI DST fix: %s", e)
            return 0
        return get_hour_offset_fix(format_time(prayers[4]), st_maghrib)

    def _get_prayer_times_ie_icci(self, target_date: date) -> dict[str, str]:
        """Get 'ie-icci' prayer times for target_date from the bundled timetable."""
        timetable = load_icci_timetable()
        if timetable is None:
            return self._get_prayer_times_standard(target_date)

        prayers = timetable[str(target_date.month)][str(target_date.day)]
        hr_offset = self._get_icci_hour_offset(prayers, target_date)
        next_date = target_date + timedelta(days=1)
        next_prayers = timetable[str(next_date.month)][str(next_date.day)]
        next_hr_offset = self._get_icci_hour_offset(next_prayers, next_date)
        midnight = get_midnight(
            get_local_datetime(target_date, prayers[4], hr_offset),
            get_local_datetime(next_date, next_prayers[1], next_hr_offset),
        )
        return {
            "Fajr": format_time(prayers[0], hr_offset),
            "Sunrise": format_time(prayers[1], hr_offset),
            "Dhuhr": format_time(prayers[2], hr_offset),
            "Asr": format_time(prayers[3], hr_offset),
            "Sunset": format_time(prayers[4], hr_offset),
            "Maghrib": format_time(prayers[4], hr_offset),
            "Isha": format_time(prayers[5], hr_offset),
            "Imsak": format_time(prayers[4], hr_offset),
            "Midnight": midnight,
        }

    def _get_prayer_times_wp_plugin(
        self, calc_method: str, target_date: date
    ) -> dict[str, str]:
        """Fetch prayer times for WordPress plugin calculation methods on target_date."""
        st_maghrib, midnight, isna_prayers = get_standard_sunset_midnight(
            self.hass.config.latitude, self.hass.config.longitude, "isna"
        )
        url = f"https://{calc_method.split('-')[1]}.ie/wp-json/dpt/v1/prayertime?filter=today"
        prayer_times_info = get_prayers_by_wp_plugin(
            url, calc_method, st_maghrib, midnight
        )
        return prayer_times_info if prayer_times_info else isna_prayers

    def get_new_prayer_times(self) -> dict[str, str]:
        """Fetch prayer times for the target date using the configured calculation method.

        To support showing the next occurrence if a prayer time has passed,
        we compute for today and adjust by adding one day when needed.
        """
        target_date = date.today()
        calc_method = self.calc_method
        if calc_method == "ie-icci":
            prayer_times = self._get_prayer_times_ie_icci(target_date)
        elif calc_method in ["ie-mcnd", "ie-hicc"]:
            prayer_times = self._get_prayer_times_wp_plugin(calc_method, target_date)
        else:
            prayer_times = self._get_prayer_times_standard(target_date)
        return prayer_times

    def _get_iqamah_times_offset(
        self, prayer_times_dt: dict[str, datetime]
    ) -> dict[str, datetime]:
        """Compute iqamah times using offset values from configuration."""
        iqamah_offsets = self.config_entry.options.get(
            CONF_IQAMAH_OFFSETS, DEFAULT_IQAMAH_OFFSETS
        )
        iqamah = {}
        for prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
            base_dt = prayer_times_dt.get(prayer)
            if base_dt:
                # Assume the offset is given in minutes and apply to the local time.
                local_time = dt_util.as_local(base_dt)
                local_iqamah = local_time + timedelta(
                    minutes=iqamah_offsets.get(prayer, 0)
                )
                iqamah[f"iqamah_{prayer}"] = dt_util.as_utc(local_iqamah)
        return iqamah

    def _get_iqamah_times_api(self) -> dict[str, datetime]:
        """Fetch iqamah times from an external API (placeholder implementation)."""
        # For example, use a custom API endpoint if provided.
        custom_api = self.config_entry.options.get("custom_iqamah_api")
        iqamah = {}
        if custom_api:
            json_resp = get_json_response(custom_api)
            if json_resp:
                try:
                    # Assume API returns times in HH:MM for each prayer.
                    for prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                        time_str = json_resp.get(prayer)
                        if time_str:
                            # Convert time_str to datetime (adjusting date if needed)
                            local_dt = dt_util.parse_datetime(
                                f"{date.today()} {time_str}"
                            )
                            if local_dt < dt_util.now():
                                local_dt = dt_util.parse_datetime(
                                    f"{date.today() + timedelta(days=1)} {time_str}"
                                )
                            iqamah[f"iqamah_{prayer}"] = dt_util.as_utc(local_dt)
                except Exception as e:
                    LOGGER.error(f"Error parsing IQamah API response: {e}")
        return iqamah

    @callback
    def async_schedule_future_update(self, midnight_dt: datetime) -> None:
        """
        Schedule the next update after midnight.
        """
        LOGGER.debug("Scheduling next update for Muslim Prayer Companion")
        now = dt_util.utcnow()
        next_update_at = (
            midnight_dt + timedelta(days=1, minutes=1)
            if now > midnight_dt
            else dt_util.start_of_local_day(now + timedelta(days=1))
        )
        LOGGER.debug(f"Next update scheduled for: {next_update_at}")
        self.event_unsub = async_track_point_in_time(
            self.hass, self.async_request_update, next_update_at
        )

    async def async_request_update(self, *_) -> None:
        """Request an update from the coordinator."""
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, any]:
        """Update sensors with new prayer, iqamah and hijri date data."""
        now = dt_util.as_local(dt_util.now())
        today = date.today()
        try:
            # Fetch prayer times (for today; will adjust if passed)
            raw_prayer_times = await self.hass.async_add_executor_job(
                self.get_new_prayer_times
            )
            hijri_date = await self.hass.async_add_executor_job(self.get_hijri_date)
        except (exceptions.InvalidResponseError, ConnError) as err:
            async_call_later(self.hass, 60, self.async_request_update)
            raise UpdateFailed from err

        prayer_times_dt: dict[str, datetime] = {}
        # For each prayer time string, determine if the time has already passed; if so, use tomorrow’s date.
        for prayer, time_str in raw_prayer_times.items():
            try:
                if isinstance(time_str, str):
                    candidate = datetime.strptime(time_str, "%H:%M")
                    candidate = candidate.replace(
                        year=today.year, month=today.month, day=today.day
                    )
                    candidate = dt_util.as_local(candidate)  # Convert to local time

                    if candidate < now:
                        candidate = candidate + timedelta(
                            days=1
                        )  # Move to next day if needed

                    prayer_times_dt[prayer] = dt_util.as_utc(
                        candidate
                    )  # Convert to UTC-aware
                else:
                    LOGGER.error(
                        f"Error parsing prayer time for {prayer}: time_str is not a string"
                    )
            except Exception as e:
                LOGGER.error(f"Error parsing prayer time for {prayer}: {e}")

        # Compute IQamah times based on the selected method.
        if self.iqamah_method == "offset":
            iqamah_times = self._get_iqamah_times_offset(prayer_times_dt)
        else:
            iqamah_times = self._get_iqamah_times_api()

        # Determine the next prayer (consider only standard prayer names).
        next_prayer_name = None
        next_prayer_time = None
        for prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
            prayer_time = prayer_times_dt.get(prayer)
            if prayer_time and prayer_time > now:
                if next_prayer_time is None or prayer_time < next_prayer_time:
                    next_prayer_time = prayer_time
                    next_prayer_name = prayer

        data: dict[str, any] = {}
        data.update(prayer_times_dt)
        data.update(iqamah_times)
        data.update(hijri_date)
        if next_prayer_time:
            data["next_prayer"] = next_prayer_time
            data["next_prayer_name"] = next_prayer_name

        # Schedule the next update at midnight.
        if "Midnight" in raw_prayer_times:
            midnight_candidate = dt_util.parse_datetime(
                f"{today} {raw_prayer_times['Midnight']}"
            )
            if midnight_candidate and midnight_candidate.tzinfo is None:
                midnight_candidate = dt_util.as_local(midnight_candidate)
            if midnight_candidate < now:
                midnight_candidate = dt_util.parse_datetime(
                    f"{today + timedelta(days=1)} {raw_prayer_times['Midnight']}"
                )
                if midnight_candidate and midnight_candidate.tzinfo is None:
                    midnight_candidate = dt_util.as_local(midnight_candidate)
            self.async_schedule_future_update(
                dt_util.as_utc(midnight_candidate)
            )  # Convert to UTC
        return data
