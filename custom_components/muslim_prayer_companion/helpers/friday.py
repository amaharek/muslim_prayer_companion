"""
Friday prayers (Jumu'ah) for a list of mosques.

A config entry can track the Friday prayers of several mosques. Each mosque is
one dict in the ``friday_mosques`` option (see :class:`FridayMosqueConfig`).
Times come either from the mosque's published API (``source`` = a registry key
of a mosque that publishes them) or from the stored ``jumuah_1``/``jumuah_2``
clock times (``source`` = ``manual``, or used as fallback when the API has none).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
import logging
import re
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from homeassistant.util import slugify

from ..api_providers.base import JumuahTime, ProviderConfig, ProviderError
from ..api_providers.ireland import IrelandProvider
from ..const import (
    CONF_FRIDAY_JUMUAH_1,
    CONF_FRIDAY_JUMUAH_2,
    CONF_FRIDAY_LABEL_1,
    CONF_FRIDAY_LABEL_2,
    CONF_FRIDAY_NAME,
    CONF_FRIDAY_SLUG,
    CONF_FRIDAY_SOURCE,
    FRIDAY_SOURCE_MANUAL,
    MAX_FRIDAY_LABEL_LENGTH,
    MAX_FRIDAY_MOSQUES,
    TIME_HHMM_RE,
)
from .registry import MOSQUES, get_mosque, is_mosque_key

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from ..api_providers.base import ProviderResult

LOGGER = logging.getLogger(__name__)

FRIDAY = 4
MAX_SLUG_LENGTH = 40
_HHMM_RE = re.compile(TIME_HHMM_RE)
_LOOSE_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*$")

TIMES_FROM_API = "api"
TIMES_FROM_MANUAL = "manual"

# Option error keys (translated in strings.json -> options.error)
ERROR_NAME_REQUIRED = "name_required"
ERROR_NAME_EXISTS = "name_exists"
ERROR_INVALID_TIME = "invalid_time"
ERROR_TIME_REQUIRED = "time_required"
ERROR_JUMUAH_ORDER = "jumuah_order"
ERROR_TOO_MANY_MOSQUES = "too_many_mosques"
ERROR_LABEL_TOO_LONG = "label_too_long"
ERROR_UNKNOWN_SOURCE = "unknown_source"


def parse_hhmm(value: Any) -> time | None:
    """Parse ``"HH:MM"`` (or ``"H:MM"``, ``"HH:MM:SS"``) into a time; None if invalid."""
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    if not isinstance(value, str):
        return None
    match = _LOOSE_TIME_RE.match(value)
    if match is None:
        return None
    hour, minute = int(match[1]), int(match[2])
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return time(hour, minute)


def normalise_hhmm(value: Any) -> str | None:
    """Return ``value`` as a canonical ``"HH:MM"`` string, or None if invalid/empty."""
    parsed = parse_hhmm(value)
    return parsed.strftime("%H:%M") if parsed else None


def is_hhmm(value: Any) -> bool:
    """Return True if ``value`` is a canonical ``HH:MM`` string."""
    return isinstance(value, str) and _HHMM_RE.match(value) is not None


def slug_for(name: str) -> str:
    """Return the stable slug for a mosque name."""
    return slugify(name)[:MAX_SLUG_LENGTH].strip("_") or "mosque"


@dataclass(frozen=True)
class FridayMosqueConfig:
    """One mosque in the Friday prayers list."""

    slug: str
    name: str
    source: str = FRIDAY_SOURCE_MANUAL
    jumuah_1: time | None = None
    jumuah_2: time | None = None
    label_1: str | None = None
    label_2: str | None = None

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> FridayMosqueConfig:
        """Build from the stored option dict, tolerating missing or odd values."""
        name = str(item.get(CONF_FRIDAY_NAME) or "Mosque").strip()
        source = str(item.get(CONF_FRIDAY_SOURCE) or FRIDAY_SOURCE_MANUAL)
        if source != FRIDAY_SOURCE_MANUAL and not is_mosque_key(source):
            source = FRIDAY_SOURCE_MANUAL
        return cls(
            slug=str(item.get(CONF_FRIDAY_SLUG) or slug_for(name)),
            name=name,
            source=source,
            jumuah_1=parse_hhmm(item.get(CONF_FRIDAY_JUMUAH_1)),
            jumuah_2=parse_hhmm(item.get(CONF_FRIDAY_JUMUAH_2)),
            label_1=_clean_label(item.get(CONF_FRIDAY_LABEL_1)),
            label_2=_clean_label(item.get(CONF_FRIDAY_LABEL_2)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the stored option dict."""
        return {
            CONF_FRIDAY_SLUG: self.slug,
            CONF_FRIDAY_NAME: self.name,
            CONF_FRIDAY_SOURCE: self.source,
            CONF_FRIDAY_JUMUAH_1: self.jumuah_1.strftime("%H:%M") if self.jumuah_1 else None,
            CONF_FRIDAY_JUMUAH_2: self.jumuah_2.strftime("%H:%M") if self.jumuah_2 else None,
            CONF_FRIDAY_LABEL_1: self.label_1,
            CONF_FRIDAY_LABEL_2: self.label_2,
        }

    @property
    def is_manual(self) -> bool:
        """Return True if times only come from the stored clock times."""
        return self.source == FRIDAY_SOURCE_MANUAL

    @property
    def manual_times(self) -> list[JumuahTime]:
        """Return the stored clock times as Jumu'ah sessions."""
        sessions: list[JumuahTime] = []
        if self.jumuah_1 is not None:
            sessions.append(JumuahTime(clock=self.jumuah_1, label=self.label_1))
        if self.jumuah_2 is not None:
            sessions.append(JumuahTime(clock=self.jumuah_2, label=self.label_2))
        return sessions

    @property
    def timezone(self) -> str | None:
        """Return the mosque's time zone when the source is a registered mosque."""
        if is_mosque_key(self.source):
            return get_mosque(self.source).timezone
        return None


def _clean_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def friday_configs(items: list[dict[str, Any]] | None) -> list[FridayMosqueConfig]:
    """Parse the stored option list."""
    return [FridayMosqueConfig.from_dict(item) for item in (items or [])]


def seed_friday_mosques(mosque_key: str | None) -> list[dict[str, Any]]:
    """Return the default Friday list: the entry's own mosque, if it is a registered one."""
    if not mosque_key or not is_mosque_key(mosque_key):
        return []
    mosque = get_mosque(mosque_key)
    return [
        FridayMosqueConfig(
            slug=slug_for(mosque.short_name),
            name=mosque.name,
            source=mosque_key if mosque.jumuah_auto else FRIDAY_SOURCE_MANUAL,
        ).to_dict()
    ]


def validate_friday_item(
    user_input: dict[str, Any],
    existing: list[dict[str, Any]],
    editing_slug: str | None = None,
) -> dict[str, str]:
    """Validate a Friday mosque form; return ``{field: error_key}`` (empty if valid)."""
    errors: dict[str, str] = {}

    name = str(user_input.get(CONF_FRIDAY_NAME) or "").strip()
    if not name:
        errors[CONF_FRIDAY_NAME] = ERROR_NAME_REQUIRED
    else:
        for item in existing:
            if item.get(CONF_FRIDAY_SLUG) == editing_slug:
                continue
            if str(item.get(CONF_FRIDAY_NAME, "")).strip().casefold() == name.casefold():
                errors[CONF_FRIDAY_NAME] = ERROR_NAME_EXISTS
                break

    if editing_slug is None and len(existing) >= MAX_FRIDAY_MOSQUES:
        errors["base"] = ERROR_TOO_MANY_MOSQUES

    source = user_input.get(CONF_FRIDAY_SOURCE) or FRIDAY_SOURCE_MANUAL
    if source != FRIDAY_SOURCE_MANUAL and not is_mosque_key(source):
        errors[CONF_FRIDAY_SOURCE] = ERROR_UNKNOWN_SOURCE

    times: dict[str, time | None] = {}
    for key in (CONF_FRIDAY_JUMUAH_1, CONF_FRIDAY_JUMUAH_2):
        raw = user_input.get(key)
        if raw in (None, ""):
            times[key] = None
            continue
        parsed = parse_hhmm(raw)
        if parsed is None:
            errors[key] = ERROR_INVALID_TIME
        times[key] = parsed

    if source == FRIDAY_SOURCE_MANUAL and times.get(CONF_FRIDAY_JUMUAH_1) is None:
        errors.setdefault(CONF_FRIDAY_JUMUAH_1, ERROR_TIME_REQUIRED)

    first, second = times.get(CONF_FRIDAY_JUMUAH_1), times.get(CONF_FRIDAY_JUMUAH_2)
    if first is not None and second is not None and second <= first:
        errors[CONF_FRIDAY_JUMUAH_2] = ERROR_JUMUAH_ORDER

    for key in (CONF_FRIDAY_LABEL_1, CONF_FRIDAY_LABEL_2):
        label = user_input.get(key)
        if isinstance(label, str) and len(label.strip()) > MAX_FRIDAY_LABEL_LENGTH:
            errors[key] = ERROR_LABEL_TOO_LONG

    return errors


def friday_item_from_input(user_input: dict[str, Any], slug: str | None = None) -> dict[str, Any]:
    """Build the stored dict from a validated form (slug kept when editing)."""
    name = str(user_input.get(CONF_FRIDAY_NAME, "")).strip()
    return FridayMosqueConfig(
        slug=slug or slug_for(name),
        name=name,
        source=user_input.get(CONF_FRIDAY_SOURCE) or FRIDAY_SOURCE_MANUAL,
        jumuah_1=parse_hhmm(user_input.get(CONF_FRIDAY_JUMUAH_1)),
        jumuah_2=parse_hhmm(user_input.get(CONF_FRIDAY_JUMUAH_2)),
        label_1=_clean_label(user_input.get(CONF_FRIDAY_LABEL_1)),
        label_2=_clean_label(user_input.get(CONF_FRIDAY_LABEL_2)),
    ).to_dict()


def next_friday_occurrence(now_utc: datetime, clock: time, tz: ZoneInfo) -> datetime:
    """Return the next Friday at ``clock`` in ``tz`` that is still ahead of ``now_utc``."""
    local_now = now_utc.astimezone(tz)
    day = local_now.date()
    days_ahead = (FRIDAY - day.weekday()) % 7
    candidate_day = day + timedelta(days=days_ahead)
    candidate = datetime.combine(candidate_day, clock, tzinfo=tz)
    if candidate <= local_now:
        candidate = datetime.combine(candidate_day + timedelta(days=7), clock, tzinfo=tz)
    return candidate.astimezone(UTC)


@dataclass
class FridayPrayerTimes:
    """Resolved Jumu'ah sessions of one mosque."""

    slug: str
    name: str
    source: str
    tz: ZoneInfo
    times: list[JumuahTime] = field(default_factory=list)
    times_from: str = TIMES_FROM_MANUAL

    def to_data(self, now_utc: datetime) -> dict[str, Any]:
        """Return the coordinator data for this mosque."""
        sessions = [
            next_friday_occurrence(now_utc, session.clock, self.tz) for session in self.times
        ]
        return {
            "name": self.name,
            "source": self.source,
            "jumuah_1": sessions[0] if sessions else None,
            "jumuah_2": sessions[1] if len(sessions) > 1 else None,
            "labels": [session.label for session in self.times[:2]],
            "times_from": self.times_from,
        }


class FridayPrayersFetcher:
    """Resolve the Jumu'ah times of every configured Friday mosque."""

    def __init__(
        self,
        session: ClientSession | None,
        configs: list[FridayMosqueConfig],
        default_tz: ZoneInfo,
    ) -> None:
        """Initialize with the HA session, the configured mosques and the entry's zone."""
        self._session = session
        self._configs = configs
        self._default_tz = default_tz
        self._providers: dict[str, IrelandProvider] = {}
        self._last_good: dict[str, list[JumuahTime]] = {}
        self._failing: set[str] = set()

    @property
    def configs(self) -> list[FridayMosqueConfig]:
        """Return the configured mosques."""
        return self._configs

    def _provider(self, key: str) -> IrelandProvider:
        if key not in self._providers:
            mosque = get_mosque(key)
            self._providers[key] = IrelandProvider(
                ProviderConfig(
                    latitude=mosque.latitude,
                    longitude=mosque.longitude,
                    calculation_method=key,
                    timezone=mosque.timezone,
                ),
                self._session,
            )
        return self._providers[key]

    async def _fetch_published(
        self, key: str, today: date, own_result: ProviderResult | None, own_key: str | None
    ) -> list[JumuahTime] | None:
        """Return the published Jumu'ah sessions for a registry mosque, or None on failure."""
        if key == own_key and own_result is not None:
            return list(own_result.jumuah)
        if not MOSQUES[key].jumuah_auto:
            return []
        try:
            result = await self._provider(key).async_fetch(today)
        except ProviderError as err:
            if key not in self._failing:
                LOGGER.warning(
                    "Could not fetch Friday prayer times from %s: %s",
                    MOSQUES[key].name,
                    err,
                )
                self._failing.add(key)
            return None
        if key in self._failing:
            LOGGER.info("Friday prayer times from %s are available again", MOSQUES[key].name)
            self._failing.discard(key)
        return list(result.jumuah)

    async def async_update(
        self,
        today: date,
        own_result: ProviderResult | None,
        own_key: str | None,
    ) -> list[FridayPrayerTimes]:
        """Resolve all configured mosques for ``today``."""
        resolved: list[FridayPrayerTimes] = []
        for config in self._configs:
            tz = ZoneInfo(config.timezone) if config.timezone else self._default_tz
            times = config.manual_times
            times_from = TIMES_FROM_MANUAL
            if not config.is_manual:
                published = await self._fetch_published(config.source, today, own_result, own_key)
                if published is None:
                    published = self._last_good.get(config.source)
                if published:
                    self._last_good[config.source] = published
                    times = published
                    times_from = TIMES_FROM_API
            resolved.append(
                FridayPrayerTimes(
                    slug=config.slug,
                    name=config.name,
                    source=config.source,
                    tz=tz,
                    times=times,
                    times_from=times_from,
                )
            )
        return resolved
