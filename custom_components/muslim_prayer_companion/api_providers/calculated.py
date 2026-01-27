"""Calculated prayer times provider using prayer-times-calculator library."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from prayer_times_calculator import PrayerTimesCalculator, exceptions

from .base import (
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

# Mapping of our method names to prayer-times-calculator method names
CALCULATION_METHODS = {
    "jafari": "jafari",
    "karachi": "karachi",
    "isna": "isna",
    "mwl": "mwl",
    "makkah": "makkah",
    "egypt": "egypt",
    "tehran": "tehran",
    "gulf": "gulf",
    "kuwait": "kuwait",
    "qatar": "qatar",
    "singapore": "singapore",
    "france": "france",
    "turkey": "turkey",
    "russia": "russia",
}


class CalculatedProvider(PrayerTimesProvider):
    """Provider that calculates prayer times using prayer-times-calculator library."""

    name = "calculated"

    def __init__(self, config: ProviderConfig, session: ClientSession | None = None):
        """Initialize the calculated provider.

        Args:
            config: Provider configuration with latitude, longitude, and calculation_method.
            session: Optional aiohttp ClientSession (not used by this provider).
        """
        super().__init__(config, session)

        # Validate calculation method
        method = config.calculation_method.lower()
        if method not in CALCULATION_METHODS:
            LOGGER.warning(
                "Unknown calculation method '%s', defaulting to 'isna'",
                config.calculation_method,
            )
            self._method = "isna"
        else:
            self._method = CALCULATION_METHODS[method]

    async def async_fetch_prayer_times(self, target_date: date) -> PrayerTimesData:
        """Fetch prayer times using the prayer-times-calculator library.

        Args:
            target_date: The date to calculate prayer times for.

        Returns:
            PrayerTimesData with all prayer times in UTC.

        Raises:
            ProviderConnectionError: If calculation fails due to connection issues.
            ProviderResponseError: If the library returns invalid data.
            ProviderValidationError: If the calculated times fail validation.
        """
        LOGGER.debug(
            "Calculating prayer times for %s at (%s, %s) using method '%s'",
            target_date,
            self.config.latitude,
            self.config.longitude,
            self._method,
        )

        try:
            calc = PrayerTimesCalculator(
                latitude=self.config.latitude,
                longitude=self.config.longitude,
                calculation_method=self._method,
                date=str(target_date),
            )
            raw_times = calc.fetch_prayer_times()
        except exceptions.InvalidResponseError as err:
            LOGGER.error("Invalid response from prayer calculator: %s", err)
            raise ProviderConnectionError(
                f"Failed to calculate prayer times: {err}"
            ) from err
        except Exception as err:
            LOGGER.error("Unexpected error calculating prayer times: %s", err)
            raise ProviderResponseError(f"Prayer calculation failed: {err}") from err

        LOGGER.debug("Raw prayer times from calculator: %s", raw_times)

        try:
            prayer_data = self._parse_times(raw_times, target_date)
        except (KeyError, ValueError) as err:
            LOGGER.error("Failed to parse prayer times: %s", err)
            raise ProviderResponseError(f"Invalid prayer times format: {err}") from err

        try:
            prayer_data.validate()
        except AssertionError as err:
            LOGGER.error("Prayer times validation failed: %s", err)
            raise ProviderValidationError(
                f"Prayer times validation failed: {err}"
            ) from err

        LOGGER.debug(
            "Calculated prayer times: Fajr=%s, Dhuhr=%s, Maghrib=%s",
            prayer_data.fajr,
            prayer_data.dhuhr,
            prayer_data.maghrib,
        )

        return prayer_data

    def _parse_times(self, raw_times: dict, target_date: date) -> PrayerTimesData:
        """Parse raw time strings into PrayerTimesData.

        Args:
            raw_times: Dictionary with prayer names as keys and "HH:MM" strings as values.
            target_date: The date for the prayer times.

        Returns:
            PrayerTimesData with UTC datetimes.
        """

        def parse_time_str(time_str: str, prayer_name: str) -> datetime:
            """Parse HH:MM string to UTC datetime."""
            if not isinstance(time_str, str):
                raise ValueError(
                    f"Expected string for {prayer_name}, got {type(time_str)}"
                )

            parts = time_str.split(":")
            if len(parts) < 2:
                raise ValueError(f"Invalid time format for {prayer_name}: {time_str}")

            hour = int(parts[0])
            minute = int(parts[1])

            # Create local datetime
            local_dt = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=hour,
                minute=minute,
            )

            # For now, treat as UTC since the library already adjusts for timezone
            # The coordinator will handle local/UTC conversion based on HA timezone
            return local_dt.replace(tzinfo=timezone.utc)

        # Parse required prayer times
        fajr = parse_time_str(raw_times.get("Fajr", ""), "Fajr")
        sunrise = parse_time_str(raw_times.get("Sunrise", ""), "Sunrise")
        dhuhr = parse_time_str(raw_times.get("Dhuhr", ""), "Dhuhr")
        asr = parse_time_str(raw_times.get("Asr", ""), "Asr")
        maghrib = parse_time_str(raw_times.get("Maghrib", ""), "Maghrib")
        isha = parse_time_str(raw_times.get("Isha", ""), "Isha")

        # Parse optional times
        midnight = None
        if "Midnight" in raw_times:
            try:
                midnight = parse_time_str(raw_times["Midnight"], "Midnight")
                # Midnight may need to be on the next day
                if midnight < fajr:
                    midnight = midnight + timedelta(days=1)
            except (ValueError, KeyError):
                LOGGER.debug("Could not parse Midnight time, skipping")

        sunset = None
        if "Sunset" in raw_times:
            try:
                sunset = parse_time_str(raw_times["Sunset"], "Sunset")
            except (ValueError, KeyError):
                LOGGER.debug("Could not parse Sunset time, using Maghrib")

        imsak = None
        if "Imsak" in raw_times:
            try:
                imsak = parse_time_str(raw_times["Imsak"], "Imsak")
            except (ValueError, KeyError):
                LOGGER.debug("Could not parse Imsak time, skipping")

        return PrayerTimesData(
            fajr=fajr,
            sunrise=sunrise,
            dhuhr=dhuhr,
            asr=asr,
            maghrib=maghrib,
            isha=isha,
            midnight=midnight,
            sunset=sunset,
            imsak=imsak,
        )

    @property
    def supports_iqamah(self) -> bool:
        """Calculated provider does not support iqamah times."""
        return False

    @property
    def supports_mosque_search(self) -> bool:
        """Calculated provider does not support mosque search."""
        return False
