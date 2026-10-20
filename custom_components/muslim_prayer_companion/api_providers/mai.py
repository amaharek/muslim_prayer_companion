"""
Parser for the Muslim Association of Ireland (Tallaght) website.

maionline.ie has no prayer-times API. Its homepage renders today's six times
server-side in a fixed table::

    <td class='prayer-cell'><div class='prayer-label fajr'>fajr</div>
      <div class='prayer-time'><span class='prayer-passed-hour'>06</span>
      <span class='prayer-separator'>:</span>
      <span class='prayer-passed-minute'>15</span></div></td>

repeated for fajr, shurooq, dhuhr, asr, maghrib and isha (the next prayer uses
``prayer-pending-*`` classes), and a ``<span class='date'>Tue, 20th October 2026``
header. The parser is strict: all six labels must be present exactly once, and
the page date must be today's date in Dublin, otherwise the provider reports an
error and the coordinator falls back to the calculated method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
import re
from typing import TYPE_CHECKING

from .base import (
    PrayerTimesData,
    ProviderResponseError,
    ProviderResult,
    ensure_after,
    local_clock_to_utc,
)

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

MAI_SOURCE_ID = "mai-website"
MAI_LABELS = ("fajr", "shurooq", "dhuhr", "asr", "maghrib", "isha")

_CELL_SPLIT_RE = re.compile(r"class=['\"]prayer-cell['\"]", re.IGNORECASE)
_LABEL_RE = re.compile(r"prayer-label\s+(?P<label>[a-z]+)", re.IGNORECASE)
_HOUR_RE = re.compile(
    r"prayer-(?:passed|pending)-hour['\"]\s*>\s*(?P<value>\d{1,2})\s*<", re.IGNORECASE
)
_MINUTE_RE = re.compile(
    r"prayer-(?:passed|pending)-minute['\"]\s*>\s*(?P<value>\d{1,2})\s*<",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"class=['\"]date['\"]\s*>\s*(?:[A-Za-z]{3,9},?\s*)?"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MaiDay:
    """The parsed homepage: the date shown and the six wall-clock times."""

    day: date | None
    times: dict[str, time] = field(default_factory=dict)


def parse_mai_date(html: str) -> date | None:
    """Return the date shown in the homepage header, or None if not found."""
    match = _DATE_RE.search(html)
    if match is None:
        return None
    try:
        return datetime.strptime(  # noqa: DTZ007
            f"{match['day']} {match['month']} {match['year']}", "%d %B %Y"
        ).date()
    except ValueError:
        return None


def parse_mai_homepage(html: str) -> MaiDay:
    """
    Parse the homepage HTML into today's six times.

    Raises:
        ValueError: If the six labelled cells are not all present exactly once.
    """
    times: dict[str, time] = {}
    for chunk in _CELL_SPLIT_RE.split(html)[1:]:
        label_match = _LABEL_RE.search(chunk)
        hour_match = _HOUR_RE.search(chunk)
        minute_match = _MINUTE_RE.search(chunk)
        if not (label_match and hour_match and minute_match):
            continue
        label = label_match["label"].lower()
        if label not in MAI_LABELS:
            continue
        if label in times:
            msg = f"prayer {label!r} appears more than once on the MAI homepage"
            raise ValueError(msg)
        try:
            times[label] = time(int(hour_match["value"]), int(minute_match["value"]))
        except ValueError as err:
            msg = f"invalid time for {label!r} on the MAI homepage: {err}"
            raise ValueError(msg) from err

    missing = [label for label in MAI_LABELS if label not in times]
    if missing:
        msg = f"MAI homepage is missing prayer times for: {', '.join(missing)}"
        raise ValueError(msg)
    return MaiDay(day=parse_mai_date(html), times=times)


def build_mai_result(parsed: MaiDay, expected_date: date, tz: ZoneInfo) -> ProviderResult:
    """
    Turn a parsed homepage into a ProviderResult for ``expected_date``.

    Raises:
        ProviderResponseError: If the page shows a different date.
    """
    if parsed.day is not None and parsed.day != expected_date:
        msg = f"maionline.ie shows {parsed.day}, expected {expected_date}"
        raise ProviderResponseError(msg)

    def at(label: str) -> datetime:
        clock = parsed.times[label]
        return local_clock_to_utc(expected_date, clock.hour, clock.minute, tz)

    maghrib = at("maghrib")
    today = PrayerTimesData(
        fajr=at("fajr"),
        sunrise=at("shurooq"),
        dhuhr=at("dhuhr"),
        asr=at("asr"),
        maghrib=maghrib,
        isha=ensure_after(at("isha"), maghrib),
        sunset=maghrib,
        source=MAI_SOURCE_ID,
    )
    return ProviderResult(today=today, source=MAI_SOURCE_ID, raw=parsed)
