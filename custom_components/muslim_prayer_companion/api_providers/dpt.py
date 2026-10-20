"""
Parser for the WordPress "Daily Prayer Time" (dpt) plugin JSON API.

Several Irish mosques (MCND, HICC, SDIC) publish
``/wp-json/dpt/v1/prayertime?filter=today``. The payload is a one-element list
with the day's times as ``"HH:MM:SS"`` strings in the mosque's local time:

    d_date, fajr_begins, fajr_jamah, sunrise, zuhr_begins, zuhr_jamah,
    asr_mithl_1, asr_mithl_2, asr_jamah, maghrib_begins, maghrib_jamah,
    isha_begins, isha_jamah, is_ramadan, hijri_date, jamah_changes,
    tomorrow (same fields for the next day), hijri_date_convert,
    jumuah (list of "HH:MM"), jumuah_label (list of labels), next_prayer

Everything here is pure and unit-testable; the HTTP side lives in ireland.py.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from itertools import zip_longest
import logging
from typing import TYPE_CHECKING, Any

from .base import (
    IqamahTimesData,
    JumuahTime,
    PrayerTimesData,
    ProviderResult,
    ensure_after,
    local_clock_to_utc,
    midpoint,
)

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)

DPT_TIME_KEYS = {
    "fajr": "fajr_begins",
    "sunrise": "sunrise",
    "dhuhr": "zuhr_begins",
    "asr": "asr_mithl_1",
    "maghrib": "maghrib_begins",
    "isha": "isha_begins",
}
DPT_JAMAH_KEYS = {
    "fajr": "fajr_jamah",
    "dhuhr": "zuhr_jamah",
    "asr": "asr_jamah",
    "maghrib": "maghrib_jamah",
    "isha": "isha_jamah",
}
# Values the plugin uses for "no time set".
EMPTY_TIMES = ("", "00:00", "00:00:00", None)
MIN_TIME_PARTS = 2


def parse_clock(value: Any) -> time | None:
    """Parse ``"HH:MM"`` or ``"HH:MM:SS"`` into a ``time``; None if unset or junk."""
    if value in EMPTY_TIMES or not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) < MIN_TIME_PARTS:
        return None
    try:
        return time(int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def payload_row(payload: Any) -> dict[str, Any]:
    """Return the day record from a dpt payload (one-element list or bare dict)."""
    if isinstance(payload, list):
        if not payload:
            msg = "Empty response from WordPress API"
            raise ValueError(msg)
        payload = payload[0]
    if not isinstance(payload, dict):
        msg = f"Unexpected dpt payload type {type(payload).__name__}"
        raise TypeError(msg)
    return payload


def row_date(row: dict[str, Any], default: date) -> date:
    """Return the date the row is for (``d_date``), or ``default`` if unreadable."""
    raw = row.get("d_date")
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            LOGGER.debug("Unreadable d_date %r, using %s", raw, default)
    return default


def parse_day(row: dict[str, Any], day: date, tz: ZoneInfo, source: str) -> PrayerTimesData:
    """Parse the six begin times of one row into UTC datetimes."""
    clocks: dict[str, time] = {}
    for name, key in DPT_TIME_KEYS.items():
        clock = parse_clock(row.get(key))
        if clock is None:
            msg = f"Missing or invalid {key!r} in dpt response"
            raise ValueError(msg)
        clocks[name] = clock

    def at(name: str) -> Any:
        clock = clocks[name]
        return local_clock_to_utc(day, clock.hour, clock.minute, tz)

    maghrib = at("maghrib")
    return PrayerTimesData(
        fajr=at("fajr"),
        sunrise=at("sunrise"),
        dhuhr=at("dhuhr"),
        asr=at("asr"),
        maghrib=maghrib,
        isha=ensure_after(at("isha"), maghrib),
        sunset=maghrib,
        source=source,
    )


def parse_jamah(row: dict[str, Any], day: date, tz: ZoneInfo) -> IqamahTimesData | None:
    """Parse the ``*_jamah`` (iqamah) times of one row; None if there are none."""
    values: dict[str, Any] = {}
    for name, key in DPT_JAMAH_KEYS.items():
        clock = parse_clock(row.get(key))
        values[name] = local_clock_to_utc(day, clock.hour, clock.minute, tz) if clock else None
    if all(value is None for value in values.values()):
        return None
    return IqamahTimesData(**values)


def parse_jumuah(row: dict[str, Any]) -> list[JumuahTime]:
    """Parse the ``jumuah`` and ``jumuah_label`` lists into Jumu'ah sessions."""
    times = row.get("jumuah") or []
    labels = row.get("jumuah_label") or []
    if not isinstance(times, list):
        return []
    if not isinstance(labels, list):
        labels = []
    sessions: list[JumuahTime] = []
    for raw_time, raw_label in zip_longest(times, labels):
        clock = parse_clock(raw_time)
        if clock is None:
            continue
        label = raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else None
        sessions.append(JumuahTime(clock=clock, label=label))
    return sessions


def parse_dpt_payload(payload: Any, target_date: date, tz: ZoneInfo, source: str) -> ProviderResult:
    """Parse a full dpt payload into a ProviderResult (today, tomorrow, iqamah, Jumu'ah)."""
    row = payload_row(payload)
    today_date = row_date(row, target_date)
    if today_date != target_date:
        LOGGER.debug(
            "dpt payload is for %s, requested %s; using the payload's date",
            today_date,
            target_date,
        )
    today = parse_day(row, today_date, tz, source)
    iqamah = parse_jamah(row, today_date, tz)

    tomorrow = None
    iqamah_tomorrow = None
    tomorrow_row = row.get("tomorrow")
    if isinstance(tomorrow_row, dict):
        tomorrow_date = row_date(tomorrow_row, today_date + timedelta(days=1))
        try:
            tomorrow = parse_day(tomorrow_row, tomorrow_date, tz, source)
        except ValueError as err:
            LOGGER.debug("Ignoring unusable 'tomorrow' in dpt payload: %s", err)
        else:
            iqamah_tomorrow = parse_jamah(tomorrow_row, tomorrow_date, tz)

    if tomorrow is not None:
        today.midnight = midpoint(today.maghrib, tomorrow.sunrise)

    return ProviderResult(
        today=today,
        tomorrow=tomorrow,
        iqamah=iqamah,
        iqamah_tomorrow=iqamah_tomorrow,
        jumuah=parse_jumuah(row),
        source=source,
        raw=row,
    )
