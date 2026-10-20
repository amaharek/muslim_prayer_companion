"""
Build the coordinator's data dict from the last provider result.

Everything here is pure: given "now", the provider result and the settings it
returns the full data dict. The coordinator calls it after every fetch and
again every minute, so sensors such as the countdown and the current prayer
period stay exact without touching the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..api_providers.base import IqamahTimesData, ProviderResult, midpoint
from ..const import (
    COUNTDOWN_FORMAT_CLOCK,
    COUNTDOWN_FORMAT_SHORT,
    IQAMAH_METHOD_API,
    IQAMAH_METHOD_DISABLED,
    IQAMAH_METHOD_MOSQUE,
    IQAMAH_METHOD_OFFSET,
    PRAYERS,
)
from .friday import FridayPrayerTimes, next_friday_occurrence
from .hijri import effective_hijri_date
from .iqamah import iqamah_from_offsets
from .special_dates import (
    days_until_ramadan,
    get_special_night,
    is_friday,
    is_ramadan,
    ramadan_day,
    upcoming_islamic_event,
)

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from .settings import Settings

ORDERED_TIMES = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
MAX_DAYS_FORWARD = 3


@dataclass
class DerivedInputs:
    """Inputs for :func:`compute_derived`."""

    now: datetime
    result: ProviderResult
    tz: ZoneInfo
    settings: Settings
    qibla: float
    provider_name: str
    friday: list[FridayPrayerTimes] = field(default_factory=list)
    iqamah_api: IqamahTimesData | None = None
    fallback_active: bool = False
    last_error: str | None = None


def _advance_past(value: datetime, now: datetime) -> datetime:
    """Add whole days to ``value`` until it is after ``now`` (bounded)."""
    for _ in range(MAX_DAYS_FORWARD):
        if value > now:
            break
        value += timedelta(days=1)
    return value


def today_midnight(result: ProviderResult) -> datetime:
    """Return today's Islamic midnight, computing it when the provider has none."""
    if result.today.midnight is not None:
        return result.today.midnight
    next_sunrise = (
        result.tomorrow.sunrise
        if result.tomorrow is not None
        else result.today.sunrise + timedelta(days=1)
    )
    return midpoint(result.today.maghrib, next_sunrise)


def next_occurrences(result: ProviderResult, now: datetime) -> dict[str, datetime]:
    """Return the next occurrence of every prayer time key, as of ``now``."""
    occurrences: dict[str, datetime] = {}
    today = result.today.to_dict()
    today["Midnight"] = today_midnight(result)
    tomorrow = result.tomorrow.to_dict() if result.tomorrow is not None else {}

    for key, value in today.items():
        if value > now:
            occurrences[key] = value
            continue
        candidate = tomorrow.get(key)
        if candidate is None or candidate <= now:
            candidate = _advance_past(value, now)
        occurrences[key] = candidate
    return occurrences


def next_prayer(occurrences: dict[str, datetime], now: datetime) -> tuple[str, datetime] | None:
    """Return the name and time of the soonest of the five prayers."""
    upcoming = [
        (occurrences[prayer], prayer)
        for prayer in PRAYERS
        if prayer in occurrences and occurrences[prayer] > now
    ]
    if not upcoming:
        return None
    when, name = min(upcoming)
    return name, when


def format_countdown(name: str, minutes: int, fmt: str) -> str:
    """Format the countdown to the next prayer."""
    minutes = max(minutes, 0)
    if fmt == COUNTDOWN_FORMAT_CLOCK:
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    if fmt == COUNTDOWN_FORMAT_SHORT:
        return str(minutes)
    unit = "minute" if minutes == 1 else "minutes"
    return f"{name} in {minutes} {unit}"


def current_prayer_period(result: ProviderResult, now: datetime, window_minutes: int) -> str:
    """
    Describe where ``now`` falls in today's prayer times.

    Returns "Before Fajr", "<Prayer>" during the first ``window_minutes`` after
    a prayer starts, "Between <X> and <Y>" otherwise, or "After Isha".
    """
    today = result.today.to_dict()
    if now < today["Fajr"]:
        return "Before Fajr"
    current = None
    following = None
    for name in ORDERED_TIMES:
        if today[name] <= now:
            current = name
        elif following is None:
            following = name
    if current is None:  # pragma: no cover - guarded by the Fajr check above
        return "Before Fajr"
    if (
        current in PRAYERS
        and window_minutes > 0
        and now < today[current] + timedelta(minutes=window_minutes)
    ):
        return current
    if following is None:
        return "After Isha"
    return f"Between {current} and {following}"


def _published_iqamah(
    published: IqamahTimesData | None,
    published_tomorrow: IqamahTimesData | None,
    now: datetime,
) -> dict[str, datetime]:
    """Return the next occurrence of each published iqamah time."""
    result: dict[str, datetime] = {}
    if published is None:
        return result
    for prayer in PRAYERS:
        value = published.get(prayer)
        if value is None:
            continue
        if value > now:
            result[prayer] = value
            continue
        tomorrow_value = published_tomorrow.get(prayer) if published_tomorrow else None
        result[prayer] = (
            tomorrow_value
            if tomorrow_value is not None and tomorrow_value > now
            else _advance_past(value, now)
        )
    return result


def resolve_iqamah(
    inp: DerivedInputs, occurrences: dict[str, datetime]
) -> tuple[dict[str, datetime], str | None]:
    """Return ``{"iqamah_<Prayer>": time}`` and the source the times came from."""
    method = inp.settings.iqamah_method
    if method == IQAMAH_METHOD_DISABLED:
        return {}, None

    # Offsets count from today's prayer while that iqamah is still ahead (the prayer
    # itself may already have started), otherwise from the next occurrence.
    today = iqamah_from_offsets(inp.result.today.to_dict(), inp.settings.iqamah_offsets)
    upcoming = iqamah_from_offsets(occurrences, inp.settings.iqamah_offsets)
    offsets = {
        prayer: today[prayer] if today.get(prayer, inp.now) > inp.now else upcoming[prayer]
        for prayer in upcoming
    }
    times: dict[str, datetime] = {}
    source = IQAMAH_METHOD_OFFSET
    if method == IQAMAH_METHOD_MOSQUE and inp.result.iqamah is not None:
        times = _published_iqamah(inp.result.iqamah, inp.result.iqamah_tomorrow, inp.now)
        source = IQAMAH_METHOD_MOSQUE
    elif method == IQAMAH_METHOD_API and inp.iqamah_api is not None:
        times = _published_iqamah(inp.iqamah_api, None, inp.now)
        source = IQAMAH_METHOD_API

    merged = {**offsets, **times}
    return {f"iqamah_{prayer}": when for prayer, when in merged.items()}, source


def juma_time(inp: DerivedInputs, occurrences: dict[str, datetime]) -> datetime:
    """Return the next Jumu'ah: provider-published, else first Friday mosque, else Friday's Dhuhr."""
    if inp.result.jumuah:
        return next_friday_occurrence(inp.now, inp.result.jumuah[0].clock, inp.tz)
    for mosque in inp.friday:
        if mosque.times:
            return next_friday_occurrence(inp.now, mosque.times[0].clock, mosque.tz)
    dhuhr_clock = occurrences["Dhuhr"].astimezone(inp.tz).time().replace(second=0, microsecond=0)
    return next_friday_occurrence(inp.now, dhuhr_clock, inp.tz)


def compute_derived(inp: DerivedInputs) -> dict[str, Any]:
    """Build the full coordinator data dict."""
    now = inp.now
    settings = inp.settings
    occurrences = next_occurrences(inp.result, now)

    data: dict[str, Any] = dict(occurrences)

    upcoming = next_prayer(occurrences, now)
    if upcoming is not None:
        name, when = upcoming
        minutes = int((when - now).total_seconds() // 60)
        data["next_prayer"] = when
        data["next_prayer_name"] = name
        data["next_prayer_minutes"] = minutes
        data["next_prayer_countdown"] = format_countdown(name, minutes, settings.countdown_format)

    data["current_prayer_period"] = current_prayer_period(
        inp.result, now, settings.prayer_window_minutes
    )

    iqamah, iqamah_source = resolve_iqamah(inp, occurrences)
    data.update(iqamah)
    data["iqamah_source"] = iqamah_source

    hijri = effective_hijri_date(
        now,
        inp.tz,
        inp.result.today.maghrib,
        change_at_maghrib=settings.hijri_change_at_maghrib,
        adjustment_days=settings.hijri_adjustment,
    )
    if hijri is not None:
        data.update(hijri.to_dict())
    local_today = now.astimezone(inp.tz).date()
    ramadan = is_ramadan(hijri)
    data["is_ramadan"] = ramadan
    data["is_friday"] = is_friday(local_today)
    data["special_night"] = get_special_night(hijri)
    data["ramadan_day"] = ramadan_day(hijri)
    data["days_until_ramadan"] = days_until_ramadan(hijri, local_today, settings.hijri_adjustment)
    event = upcoming_islamic_event(hijri, local_today, settings.hijri_adjustment)
    data["upcoming_islamic_event"] = event.name if event else None
    data["upcoming_islamic_event_date"] = event.date if event else None
    data["upcoming_islamic_event_days"] = event.days_until if event else None
    data["imsak"] = occurrences["Fajr"] - timedelta(minutes=settings.imsak_minutes)
    data["iftar"] = occurrences["Maghrib"] if ramadan else None

    data["juma_time"] = juma_time(inp, occurrences)
    data["friday"] = {mosque.slug: mosque.to_data(now) for mosque in inp.friday}

    data["qibla_direction"] = inp.qibla
    data["location_name"] = settings.location_name
    data["source"] = inp.result.source
    data["provider"] = inp.provider_name
    data["fallback_active"] = inp.fallback_active
    data["last_error"] = inp.last_error
    return data
