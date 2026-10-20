"""Base classes and data models for prayer times providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from aiohttp import ClientSession


def local_clock_to_utc(day: date, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    """Combine a day and a wall-clock time in ``tz`` into a UTC datetime."""
    return datetime.combine(day, time(hour, minute), tzinfo=tz).astimezone(UTC)


def ensure_after(value: datetime, reference: datetime) -> datetime:
    """Return ``value`` moved forward by one day if it is not after ``reference``."""
    if value <= reference:
        return value + timedelta(days=1)
    return value


def midpoint(start: datetime, end: datetime) -> datetime:
    """
    Return the instant halfway between two aware datetimes, to the minute.

    The arithmetic is done in UTC so a DST change between the two instants is
    counted correctly; the result is floored to the minute like a timetable.
    """
    start_utc = start.astimezone(UTC)
    middle = start_utc + (end.astimezone(UTC) - start_utc) / 2
    return middle.replace(second=0, microsecond=0)


@dataclass
class PrayerTimesData:
    """
    Standardized prayer times - all providers MUST populate these fields.

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
    source: str | None = None

    def validate(self) -> None:
        """
        Validate prayer times are in correct order and timezone-aware.

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

        for name, value in required_times:
            if value.tzinfo is None:
                msg = f"Prayer time '{name}' must be timezone-aware, got naive datetime"
                raise AssertionError(msg)

        times = [t for _, t in required_times]
        for i in range(len(times) - 1):
            if times[i] >= times[i + 1]:
                msg = (
                    f"Prayer times out of order: {required_times[i][0]} ({times[i]}) "
                    f">= {required_times[i + 1][0]} ({times[i + 1]})"
                )
                raise AssertionError(msg)

        if self.midnight is not None and self.midnight.tzinfo is None:
            msg = "Midnight time must be timezone-aware"
            raise AssertionError(msg)

        if self.imsak is not None:
            if self.imsak.tzinfo is None:
                msg = "Imsak time must be timezone-aware"
                raise AssertionError(msg)
            if self.imsak >= self.fajr:
                msg = f"Imsak ({self.imsak}) must be before Fajr ({self.fajr})"
                raise AssertionError(msg)

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

        # Sunset is typically the same as Maghrib
        result["Sunset"] = self.sunset if self.sunset is not None else self.maghrib

        return result

    def get(self, key: str) -> datetime | None:
        """Return a time by its Home Assistant key (``"Fajr"``, ``"Midnight"``...)."""
        return self.to_dict().get(key)


@dataclass
class IqamahTimesData:
    """
    Standardized iqamah times.

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
        """
        Validate iqamah times are timezone-aware.

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

        for name, value in times:
            if value is not None and value.tzinfo is None:
                msg = f"Iqamah time '{name}' must be timezone-aware, got naive datetime"
                raise AssertionError(msg)

    def to_dict(self) -> dict[str, datetime]:
        """Convert to dictionary with Home Assistant compatible keys."""
        result: dict[str, datetime] = {}

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

    def get(self, prayer: str) -> datetime | None:
        """Return the iqamah time for a prayer name such as ``"Fajr"``."""
        return getattr(self, prayer.lower(), None)


@dataclass(frozen=True)
class JumuahTime:
    """One Jumu'ah (Friday prayer) session, as wall-clock time at the mosque."""

    clock: time
    label: str | None = None


@dataclass
class ProviderResult:
    """Everything a provider knows about one day, fetched in a single call."""

    today: PrayerTimesData
    tomorrow: PrayerTimesData | None = None
    iqamah: IqamahTimesData | None = None
    iqamah_tomorrow: IqamahTimesData | None = None
    jumuah: list[JumuahTime] = field(default_factory=list)
    source: str = "unknown"
    raw: Any = None


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
    short_name: str | None = None


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
    """
    Abstract base class for prayer times providers.

    All providers must implement this interface to ensure consistent
    data formats across different data sources.
    """

    name: str = "base"
    source_id: str = "unknown"

    def __init__(self, config: ProviderConfig, session: ClientSession | None = None) -> None:
        """
        Initialize the provider.

        Args:
            config: Provider configuration.
            session: Optional aiohttp ClientSession for HTTP requests.
        """
        self.config = config
        self._session = session

    @abstractmethod
    async def async_fetch_prayer_times(self, target_date: date) -> PrayerTimesData:
        """
        Fetch prayer times for a specific date.

        Args:
            target_date: The date to fetch prayer times for.

        Returns:
            PrayerTimesData with all prayer times in UTC.

        Raises:
            ProviderError: If fetching fails.
        """

    async def async_fetch_iqamah_times(self, target_date: date) -> IqamahTimesData | None:
        """
        Fetch iqamah times for a specific date.

        Default implementation returns None. Override in providers
        that support iqamah times.
        """
        return None

    async def async_fetch(self, target_date: date) -> ProviderResult:
        """
        Fetch everything for ``target_date`` and, best effort, the day after.

        The default composes the single-day methods; providers that get all
        of it from one request override this to fetch once.
        """
        today = await self.async_fetch_prayer_times(target_date)
        tomorrow: PrayerTimesData | None
        try:
            tomorrow = await self.async_fetch_prayer_times(target_date + timedelta(days=1))
        except ProviderError:
            tomorrow = None
        iqamah = await self.async_fetch_iqamah_times(target_date) if self.supports_iqamah else None
        return ProviderResult(today=today, tomorrow=tomorrow, iqamah=iqamah, source=self.source_id)

    async def async_search_mosques(
        self, latitude: float, longitude: float, radius_km: float = 10
    ) -> list[MosqueInfo]:
        """
        Search for mosques near a location.

        Default implementation returns empty list. Override in providers
        that support mosque search.
        """
        return []

    @property
    def supports_iqamah(self) -> bool:
        """Return True if this provider supports iqamah times."""
        return False

    @property
    def supports_jumuah(self) -> bool:
        """Return True if this provider publishes Jumu'ah times."""
        return False

    @property
    def supports_mosque_search(self) -> bool:
        """Return True if this provider supports mosque search."""
        return False

    @property
    def supports_any_date(self) -> bool:
        """Return True if the provider can produce times for an arbitrary date."""
        return False


class ProviderError(Exception):
    """Base exception for provider errors."""


class ProviderConnectionError(ProviderError):
    """Raised when connection to provider fails."""


class ProviderResponseError(ProviderError):
    """Raised when provider returns invalid response."""


class ProviderValidationError(ProviderError):
    """Raised when data validation fails."""
