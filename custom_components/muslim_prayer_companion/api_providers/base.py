"""Base classes and data models for prayer times providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp import ClientSession


@dataclass
class PrayerTimesData:
    """Standardized prayer times - all providers MUST populate these fields.

    All datetime fields must be timezone-aware (UTC).
    """

    fajr: datetime
    sunrise: datetime
    dhuhr: datetime
    asr: datetime
    maghrib: datetime
    isha: datetime
    midnight: datetime | None = None
    imsak: datetime | None = None
    sunset: datetime | None = None

    def validate(self) -> None:
        """Validate prayer times are in correct order and timezone-aware.

        Raises:
            AssertionError: If validation fails.
        """
        required_times = [
            ("fajr", self.fajr),
            ("sunrise", self.sunrise),
            ("dhuhr", self.dhuhr),
            ("asr", self.asr),
            ("maghrib", self.maghrib),
            ("isha", self.isha),
        ]

        # Check all required times are timezone-aware
        for name, time in required_times:
            if time.tzinfo is None:
                raise AssertionError(
                    f"Prayer time '{name}' must be timezone-aware, got naive datetime"
                )

        # Check chronological order
        times = [t for _, t in required_times]
        for i in range(len(times) - 1):
            if times[i] >= times[i + 1]:
                raise AssertionError(
                    f"Prayer times out of order: {required_times[i][0]} ({times[i]}) "
                    f">= {required_times[i+1][0]} ({times[i+1]})"
                )

        # Validate optional times if present
        if self.midnight is not None and self.midnight.tzinfo is None:
            raise AssertionError("Midnight time must be timezone-aware")

        if self.imsak is not None:
            if self.imsak.tzinfo is None:
                raise AssertionError("Imsak time must be timezone-aware")
            if self.imsak >= self.fajr:
                raise AssertionError(
                    f"Imsak ({self.imsak}) must be before Fajr ({self.fajr})"
                )

    def to_dict(self) -> dict[str, datetime]:
        """Convert to dictionary with Home Assistant compatible keys."""
        result = {
            "Fajr": self.fajr,
            "Sunrise": self.sunrise,
            "Dhuhr": self.dhuhr,
            "Asr": self.asr,
            "Maghrib": self.maghrib,
            "Isha": self.isha,
        }

        if self.midnight is not None:
            result["Midnight"] = self.midnight

        if self.imsak is not None:
            result["Imsak"] = self.imsak

        if self.sunset is not None:
            result["Sunset"] = self.sunset
        else:
            # Sunset is typically same as Maghrib
            result["Sunset"] = self.maghrib

        return result


@dataclass
class IqamahTimesData:
    """Standardized iqamah times.

    All datetime fields must be timezone-aware (UTC) if set.
    """

    fajr: datetime | None = None
    dhuhr: datetime | None = None
    asr: datetime | None = None
    maghrib: datetime | None = None
    isha: datetime | None = None
    juma: datetime | None = None
    juma_khutbah: datetime | None = None

    def validate(self) -> None:
        """Validate iqamah times are timezone-aware.

        Raises:
            AssertionError: If validation fails.
        """
        times = [
            ("fajr", self.fajr),
            ("dhuhr", self.dhuhr),
            ("asr", self.asr),
            ("maghrib", self.maghrib),
            ("isha", self.isha),
            ("juma", self.juma),
            ("juma_khutbah", self.juma_khutbah),
        ]

        for name, time in times:
            if time is not None and time.tzinfo is None:
                raise AssertionError(
                    f"Iqamah time '{name}' must be timezone-aware, got naive datetime"
                )

    def to_dict(self) -> dict[str, datetime]:
        """Convert to dictionary with Home Assistant compatible keys."""
        result = {}

        if self.fajr is not None:
            result["iqamah_Fajr"] = self.fajr
        if self.dhuhr is not None:
            result["iqamah_Dhuhr"] = self.dhuhr
        if self.asr is not None:
            result["iqamah_Asr"] = self.asr
        if self.maghrib is not None:
            result["iqamah_Maghrib"] = self.maghrib
        if self.isha is not None:
            result["iqamah_Isha"] = self.isha
        if self.juma is not None:
            result["juma_time"] = self.juma
        if self.juma_khutbah is not None:
            result["juma_khutbah"] = self.juma_khutbah

        return result


@dataclass
class MosqueInfo:
    """Standardized mosque metadata."""

    name: str
    uuid: str
    latitude: float
    longitude: float
    address: str | None = None
    city: str | None = None
    country: str | None = None
    website: str | None = None
    timezone: str | None = None


@dataclass
class ProviderConfig:
    """Configuration for a prayer times provider."""

    latitude: float
    longitude: float
    calculation_method: str
    timezone: str
    mosque_id: str | None = None
    api_key: str | None = None


class PrayerTimesProvider(ABC):
    """Abstract base class for prayer times providers.

    All providers must implement this interface to ensure consistent
    data formats across different data sources.
    """

    name: str = "base"

    def __init__(self, config: ProviderConfig, session: ClientSession | None = None):
        """Initialize the provider.

        Args:
            config: Provider configuration.
            session: Optional aiohttp ClientSession for HTTP requests.
        """
        self.config = config
        self._session = session

    @abstractmethod
    async def async_fetch_prayer_times(self, target_date: date) -> PrayerTimesData:
        """Fetch prayer times for a specific date.

        Args:
            target_date: The date to fetch prayer times for.

        Returns:
            PrayerTimesData with all prayer times in UTC.

        Raises:
            ProviderError: If fetching fails.
        """

    async def async_fetch_iqamah_times(
        self, target_date: date
    ) -> IqamahTimesData | None:
        """Fetch iqamah times for a specific date.

        Default implementation returns None. Override in providers
        that support iqamah times.

        Args:
            target_date: The date to fetch iqamah times for.

        Returns:
            IqamahTimesData or None if not supported.
        """
        return None

    async def async_search_mosques(
        self, latitude: float, longitude: float, radius_km: float = 10
    ) -> list[MosqueInfo]:
        """Search for mosques near a location.

        Default implementation returns empty list. Override in providers
        that support mosque search.

        Args:
            latitude: Latitude of search center.
            longitude: Longitude of search center.
            radius_km: Search radius in kilometers.

        Returns:
            List of MosqueInfo objects.
        """
        return []

    @property
    def supports_iqamah(self) -> bool:
        """Return True if this provider supports iqamah times."""
        return False

    @property
    def supports_mosque_search(self) -> bool:
        """Return True if this provider supports mosque search."""
        return False


class ProviderError(Exception):
    """Base exception for provider errors."""


class ProviderConnectionError(ProviderError):
    """Raised when connection to provider fails."""


class ProviderResponseError(ProviderError):
    """Raised when provider returns invalid response."""


class ProviderValidationError(ProviderError):
    """Raised when data validation fails."""
