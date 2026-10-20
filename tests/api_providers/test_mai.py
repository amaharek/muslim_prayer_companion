"""Tests for the Muslim Association of Ireland (Tallaght) homepage parser."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from custom_components.muslim_prayer_companion.api_providers.base import (
    ProviderResponseError,
)
from custom_components.muslim_prayer_companion.api_providers.mai import (
    MAI_LABELS,
    MaiDay,
    build_mai_result,
    parse_mai_date,
    parse_mai_homepage,
)

from ..conftest import load_fixture

DUBLIN = ZoneInfo("Europe/Dublin")
EXPECTED = {
    "fajr": time(6, 15),
    "shurooq": time(7, 56),
    "dhuhr": time(13, 11),
    "asr": time(15, 46),
    "maghrib": time(18, 22),
    "isha": time(19, 56),
}


def test_parse_captured_homepage() -> None:
    """The capture of 20 Oct 2026 parses into the six published times."""
    parsed = parse_mai_homepage(load_fixture("mai_home.html"))
    assert parsed.day == date(2026, 10, 20)
    assert parsed.times == EXPECTED


def test_pending_and_passed_classes_both_parse() -> None:
    """The next prayer uses prayer-pending-* classes; earlier ones prayer-passed-*."""
    html = load_fixture("mai_home.html")
    assert "prayer-pending-hour" in html
    assert "prayer-passed-hour" in html
    assert len(parse_mai_homepage(html).times) == len(MAI_LABELS)


def test_double_quotes_and_whitespace() -> None:
    """Attribute quoting and whitespace variations do not matter."""
    cells = "".join(
        f'<td class="prayer-cell"><div class="prayer-label {label}">{label}</div>'
        f'<div class="prayer-time"><span class="prayer-passed-hour"> {clock.hour:02d} </span>'
        f'<span class="prayer-separator">:</span>'
        f'<span class="prayer-passed-minute"> {clock.minute:02d} </span></div></td>'
        for label, clock in EXPECTED.items()
    )
    parsed = parse_mai_homepage(f"<table><tr>{cells}</tr></table>")
    assert parsed.times == EXPECTED
    assert parsed.day is None


def test_missing_label_raises() -> None:
    """A page without all six prayers is rejected."""
    html = load_fixture("mai_home.html").replace("prayer-label asr", "prayer-label other")
    with pytest.raises(ValueError, match="missing prayer times for: asr"):
        parse_mai_homepage(html)


def test_duplicate_label_raises() -> None:
    """A prayer appearing twice is rejected rather than silently overwritten."""
    html = load_fixture("mai_home.html").replace("prayer-label dhuhr", "prayer-label asr")
    with pytest.raises(ValueError, match="more than once"):
        parse_mai_homepage(html)


def test_unrelated_page_raises() -> None:
    """A page without the table (for example an error page) is rejected."""
    with pytest.raises(ValueError, match="missing prayer times"):
        parse_mai_homepage("<html><body><h1>Maintenance</h1></body></html>")


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ("<span class='date'>Tue, 20th October 2026<br />", date(2026, 10, 20)),
        ('<span class="date">1 March 2027</span>', date(2027, 3, 1)),
        ("<span class='date'>Fri, 2nd January 2026", date(2026, 1, 2)),
        ("<span class='date'>soon</span>", None),
        ("<span class='other'>Tue, 20th October 2026</span>", None),
    ],
)
def test_parse_mai_date(snippet: str, expected: date | None) -> None:
    """The header date is parsed when present."""
    assert parse_mai_date(snippet) == expected


def test_build_result_for_today() -> None:
    """Times are converted from Irish clock time to UTC; only today is available."""
    parsed = parse_mai_homepage(load_fixture("mai_home.html"))
    result = build_mai_result(parsed, date(2026, 10, 20), DUBLIN)
    assert result.source == "mai-website"
    assert result.today.fajr == datetime(2026, 10, 20, 5, 15, tzinfo=UTC)
    assert result.today.maghrib == datetime(2026, 10, 20, 17, 22, tzinfo=UTC)
    assert result.today.sunset == result.today.maghrib
    assert result.tomorrow is None
    assert result.today.midnight is None
    assert result.jumuah == []
    result.today.validate()


def test_build_result_rejects_other_date() -> None:
    """A page showing another day is not used for today."""
    parsed = parse_mai_homepage(load_fixture("mai_home.html"))
    with pytest.raises(ProviderResponseError, match="shows 2026-10-20, expected 2026-10-21"):
        build_mai_result(parsed, date(2026, 10, 21), DUBLIN)


def test_build_result_without_date_is_accepted() -> None:
    """When the page has no readable date, the requested date is trusted."""
    result = build_mai_result(MaiDay(day=None, times=EXPECTED), date(2026, 10, 21), DUBLIN)
    assert result.today.fajr.astimezone(DUBLIN).date() == date(2026, 10, 21)
