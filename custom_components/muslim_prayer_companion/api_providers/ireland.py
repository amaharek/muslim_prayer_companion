"""Ireland mosque API providers (ICCI, MCND, HICC, SDIC)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

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


# Ireland API configurations
IRELAND_APIS = {
    "ie-icci": {
        "name": "Islamic Cultural Centre of Ireland (ICCI)",
        "url": "https://islamireland.ie/api/timetable/",
        "type": "icci",
        "mosque_info": MosqueInfo(
            name="Islamic Cultural Centre of Ireland",
            uuid="ie-icci",
            latitude=53.2663,
            longitude=-6.2135,
            address="19 Roebuck Road, Clonskeagh",
            city="Dublin",
            country="Ireland",
            website="https://islamireland.ie",
            timezone="Europe/Dublin",
        ),
    },
    "ie-mcnd": {
        "name": "Muslim Community North Dublin (MCND)",
        "url": "https://mcnd.ie/wp-json/dpt/v1/prayertime?filter=today",
        "type": "wordpress",
        "mosque_info": MosqueInfo(
            name="Muslim Community North Dublin",
            uuid="ie-mcnd",
            latitude=53.4023,
            longitude=-6.1756,
            address="Rolestown",
            city="Dublin",
            country="Ireland",
            website="https://mcnd.ie",
            timezone="Europe/Dublin",
        ),
    },
    "ie-hicc": {
        "name": "Hansfield Islamic Cultural Centre (HICC)",
        "url": "https://hicc.ie/wp-json/dpt/v1/prayertime?filter=today",
        "type": "wordpress",
        "mosque_info": MosqueInfo(
            name="Hansfield Islamic Cultural Centre",
            uuid="ie-hicc",
            latitude=53.3940,
            longitude=-6.4258,
            address="Hansfield",
            city="Dublin",
            country="Ireland",
            website="https://hicc.ie",
            timezone="Europe/Dublin",
        ),
    },
    "ie-sdic": {
        "name": "South Dublin Islamic Centre (SDIC)",
        "url": "https://sdic.ie/wp-json/dpt/v1/prayertime?filter=today",
        "type": "wordpress",
        "mosque_info": MosqueInfo(
            name="South Dublin Islamic Centre",
            uuid="ie-sdic",
            latitude=53.2870,
            longitude=-6.3722,
            address="Tallaght",
            city="Dublin",
            country="Ireland",
            website="https://sdic.ie",
            timezone="Europe/Dublin",
        ),
    },
}


class IrelandProvider(PrayerTimesProvider):
    """Unified provider for Ireland mosque APIs (ICCI, MCND, HICC, SDIC)."""

    name = "ireland"

    def __init__(self, config: ProviderConfig, session: ClientSession | None = None):
        """Initialize the Ireland provider.

        Args:
            config: Provider configuration with calculation_method set to ireland API key.
            session: Optional aiohttp ClientSession for HTTP requests.
        """
        super().__init__(config, session)

        api_key = config.calculation_method.lower()
        if api_key not in IRELAND_APIS:
            raise ValueError(
                f"Unknown Ireland API: {api_key}. "
                f"Valid options: {', '.join(IRELAND_APIS.keys())}"
            )

        self._api_key = api_key
        self._api_config = IRELAND_APIS[api_key]
        self._owns_session = False

    @property
    def api_name(self) -> str:
        """Return the API name."""
        return self._api_config["name"]

    @property
    def mosque_info(self) -> MosqueInfo:
        """Return mosque information for this API."""
        return self._api_config["mosque_info"]

    async def _ensure_session(self) -> ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def _fetch_json(self, url: str) -> Any:
        """Fetch JSON from URL.

        Args:
            url: URL to fetch.

        Returns:
            Parsed JSON response.

        Raises:
            ProviderConnectionError: If request fails.
            ProviderResponseError: If response is invalid.
        """
        session = await self._ensure_session()

        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise ProviderConnectionError(
                        f"API request failed with status {response.status}"
                    )
                return await response.json()
        except aiohttp.ClientError as err:
            raise ProviderConnectionError(f"Failed to connect to API: {err}") from err
        except Exception as err:
            raise ProviderResponseError(f"Failed to parse API response: {err}") from err

    async def async_fetch_prayer_times(self, target_date: date) -> PrayerTimesData:
        """Fetch prayer times from the Ireland API.

        Args:
            target_date: The date to fetch prayer times for.

        Returns:
            PrayerTimesData with all prayer times in UTC.

        Raises:
            ProviderConnectionError: If API request fails.
            ProviderResponseError: If API returns invalid data.
            ProviderValidationError: If times fail validation.
        """
        LOGGER.debug(
            "Fetching prayer times from %s for %s",
            self.api_name,
            target_date,
        )

        url = self._api_config["url"]
        api_type = self._api_config["type"]

        try:
            json_response = await self._fetch_json(url)
        except (ProviderConnectionError, ProviderResponseError):
            raise

        LOGGER.debug("Raw API response from %s: %s", self.api_name, json_response)

        try:
            if api_type == "icci":
                prayer_data = self._parse_icci_response(json_response, target_date)
            else:  # wordpress
                prayer_data = self._parse_wordpress_response(json_response, target_date)
        except (KeyError, ValueError, TypeError) as err:
            LOGGER.error("Failed to parse %s response: %s", self.api_name, err)
            raise ProviderResponseError(
                f"Invalid response from {self.api_name}: {err}"
            ) from err

        try:
            prayer_data.validate()
        except AssertionError as err:
            LOGGER.error(
                "Prayer times validation failed for %s: %s", self.api_name, err
            )
            raise ProviderValidationError(
                f"Invalid prayer times from {self.api_name}: {err}"
            ) from err

        LOGGER.info(
            "Successfully fetched prayer times from %s: Fajr=%s, Maghrib=%s",
            self.api_name,
            prayer_data.fajr,
            prayer_data.maghrib,
        )

        return prayer_data

    async def async_fetch_iqamah_times(
        self, target_date: date
    ) -> IqamahTimesData | None:
        """Fetch iqamah times from WordPress-based APIs.

        Only WordPress-based APIs (MCND, HICC, SDIC) provide iqamah times.

        Args:
            target_date: The date to fetch iqamah times for.

        Returns:
            IqamahTimesData or None if not available.
        """
        if self._api_config["type"] != "wordpress":
            return None

        url = self._api_config["url"]

        try:
            json_response = await self._fetch_json(url)
            return self._parse_wordpress_iqamah(json_response, target_date)
        except Exception as err:
            LOGGER.warning(
                "Failed to fetch iqamah times from %s: %s", self.api_name, err
            )
            return None

    def _parse_icci_response(
        self, json_response: dict, target_date: date
    ) -> PrayerTimesData:
        """Parse ICCI timetable API response.

        ICCI returns a nested structure:
        {
            "timetable": {
                "1": {  # month
                    "1": [hour, minute] * 6,  # day: [fajr, sunrise, dhuhr, asr, maghrib, isha]
                    ...
                },
                ...
            }
        }
        """
        timetable = json_response.get("timetable", {})

        # ICCI uses non-zero-padded month/day
        month_key = str(target_date.month)
        day_key = str(target_date.day)

        month_data = timetable.get(month_key, {})
        day_prayers = month_data.get(day_key)

        if not day_prayers:
            raise ValueError(
                f"No prayer times found for {target_date} in ICCI response"
            )

        if len(day_prayers) < 6:
            raise ValueError(
                f"Incomplete prayer times for {target_date}: expected 6, got {len(day_prayers)}"
            )

        def time_list_to_datetime(
            time_list: list[int], is_next_day: bool = False
        ) -> datetime:
            """Convert [hour, minute] to UTC datetime."""
            hour, minute = time_list[0], time_list[1]
            dt = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=hour,
                minute=minute,
                tzinfo=timezone.utc,
            )
            if is_next_day:
                dt = dt + timedelta(days=1)
            return dt

        fajr = time_list_to_datetime(day_prayers[0])
        sunrise = time_list_to_datetime(day_prayers[1])
        dhuhr = time_list_to_datetime(day_prayers[2])
        asr = time_list_to_datetime(day_prayers[3])
        maghrib = time_list_to_datetime(day_prayers[4])
        isha = time_list_to_datetime(day_prayers[5])

        # Calculate midnight (midpoint between maghrib and next fajr)
        midnight = maghrib + timedelta(hours=6)  # Approximate

        return PrayerTimesData(
            fajr=fajr,
            sunrise=sunrise,
            dhuhr=dhuhr,
            asr=asr,
            maghrib=maghrib,
            isha=isha,
            midnight=midnight,
            sunset=maghrib,
        )

    def _parse_wordpress_response(
        self, json_response: list | dict, target_date: date
    ) -> PrayerTimesData:
        """Parse WordPress Daily Prayer Time plugin response.

        WordPress DPT plugin returns:
        [
            {
                "fajr_begins": "06:45:00",
                "fajr_jamah": "07:00:00",
                "sunrise": "08:30:00",
                "zuhr_begins": "12:30:00",
                "zuhr_jamah": "13:30:00",
                "asr_mithl_1": "14:45:00",
                "asr_jamah": "15:30:00",
                "maghrib_begins": "17:00:00",
                "maghrib_jamah": "17:05:00",
                "isha_begins": "18:30:00",
                "isha_jamah": "19:30:00",
                ...
            }
        ]
        """
        if isinstance(json_response, list):
            if not json_response:
                raise ValueError("Empty response from WordPress API")
            prayers = json_response[0]
        else:
            prayers = json_response

        def time_str_to_datetime(time_str: str, is_next_day: bool = False) -> datetime:
            """Convert HH:MM:SS or HH:MM to UTC datetime."""
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1])

            dt = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=hour,
                minute=minute,
                tzinfo=timezone.utc,
            )
            if is_next_day:
                dt = dt + timedelta(days=1)
            return dt

        # Map WordPress field names to standard names
        fajr = time_str_to_datetime(prayers["fajr_begins"])
        sunrise = time_str_to_datetime(prayers["sunrise"])
        dhuhr = time_str_to_datetime(prayers["zuhr_begins"])
        asr = time_str_to_datetime(prayers["asr_mithl_1"])
        maghrib = time_str_to_datetime(prayers["maghrib_begins"])
        isha = time_str_to_datetime(prayers["isha_begins"])

        # Calculate midnight
        midnight = maghrib + timedelta(hours=6)  # Approximate

        return PrayerTimesData(
            fajr=fajr,
            sunrise=sunrise,
            dhuhr=dhuhr,
            asr=asr,
            maghrib=maghrib,
            isha=isha,
            midnight=midnight,
            sunset=maghrib,
        )

    def _parse_wordpress_iqamah(
        self, json_response: list | dict, target_date: date
    ) -> IqamahTimesData:
        """Parse iqamah times from WordPress response."""
        if isinstance(json_response, list):
            if not json_response:
                return IqamahTimesData()
            prayers = json_response[0]
        else:
            prayers = json_response

        def time_str_to_datetime(time_str: str | None) -> datetime | None:
            """Convert HH:MM:SS or HH:MM to UTC datetime."""
            if not time_str:
                return None

            try:
                parts = time_str.split(":")
                hour = int(parts[0])
                minute = int(parts[1])

                return datetime(
                    year=target_date.year,
                    month=target_date.month,
                    day=target_date.day,
                    hour=hour,
                    minute=minute,
                    tzinfo=timezone.utc,
                )
            except (ValueError, IndexError):
                return None

        return IqamahTimesData(
            fajr=time_str_to_datetime(prayers.get("fajr_jamah")),
            dhuhr=time_str_to_datetime(prayers.get("zuhr_jamah")),
            asr=time_str_to_datetime(prayers.get("asr_jamah")),
            maghrib=time_str_to_datetime(prayers.get("maghrib_jamah")),
            isha=time_str_to_datetime(prayers.get("isha_jamah")),
            juma=time_str_to_datetime(prayers.get("jumuah_time")),
        )

    async def async_search_mosques(
        self, latitude: float, longitude: float, radius_km: float = 10
    ) -> list[MosqueInfo]:
        """Return list of Ireland mosques.

        This provider doesn't do distance-based search, just returns
        all known Ireland mosques.
        """
        return [api["mosque_info"] for api in IRELAND_APIS.values()]

    @property
    def supports_iqamah(self) -> bool:
        """WordPress-based APIs support iqamah times."""
        return self._api_config["type"] == "wordpress"

    @property
    def supports_mosque_search(self) -> bool:
        """Ireland provider supports mosque listing."""
        return True

    async def close(self) -> None:
        """Close the aiohttp session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._owns_session = False
