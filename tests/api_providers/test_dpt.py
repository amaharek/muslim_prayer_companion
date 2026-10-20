"""Tests for the WordPress Daily Prayer Time (dpt) payload parser."""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from custom_components.muslim_prayer_companion.api_providers.base import (
    JumuahTime,
    midpoint,
)
from custom_components.muslim_prayer_companion.api_providers.dpt import (
    parse_clock,
    parse_dpt_payload,
    parse_jumuah,
    payload_row,
)

from ..conftest import load_json_fixture

DUBLIN = ZoneInfo("Europe/Dublin")
TODAY = date(2026, 10, 20)


def local(value: datetime) -> str:
    return value.astimezone(DUBLIN).strftime("%H:%M")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("13:30", time(13, 30)),
        ("13:30:00", time(13, 30)),
        (" 6:05 ", time(6, 5)),
        ("00:00:00", None),
        ("00:00", None),
        ("", None),
        (None, None),
        ("junk", None),
        ("25:00", None),
        (1330, None),
    ],
)
def test_parse_clock(value: object, expected: time | None) -> None:
    """Clock strings are parsed leniently; unset markers give None."""
    if expected is None and value == "25:00":
        with pytest.raises(ValueError):
            time(25, 0)
    assert parse_clock(value) == expected


def test_parse_hicc_payload() -> None:
    """The HICC capture yields today, tomorrow, iqamah and two Jumu'ah sessions."""
    payload = load_json_fixture("dpt_hicc.json")
    result = parse_dpt_payload(payload, TODAY, DUBLIN, "hicc-api")
    row = payload[0]

    assert result.source == "hicc-api"
    assert result.today.source == "hicc-api"
    assert local(result.today.fajr) == row["fajr_begins"][:5]
    assert local(result.today.maghrib) == "18:23"
    assert result.today.maghrib == datetime(2026, 10, 20, 17, 23, tzinfo=UTC)
    assert result.today.sunset == result.today.maghrib
    result.today.validate()

    assert result.tomorrow is not None
    assert result.tomorrow.fajr.astimezone(DUBLIN).date() == date(2026, 10, 21)
    assert local(result.tomorrow.fajr) == row["tomorrow"]["fajr_begins"][:5]
    result.tomorrow.validate()

    assert result.today.midnight is not None
    assert result.today.midnight == midpoint(result.today.maghrib, result.tomorrow.sunrise)
    assert result.today.midnight.second == 0

    assert result.iqamah is not None
    assert local(result.iqamah.fajr) == row["fajr_jamah"][:5]
    assert result.iqamah_tomorrow is not None
    assert local(result.iqamah_tomorrow.fajr) == row["tomorrow"]["fajr_jamah"][:5]

    assert result.jumuah == [
        JumuahTime(clock=time(13, 30), label="Men Only"),
        JumuahTime(clock=time(14, 30), label="Men & Women"),
    ]
    assert result.raw is row


def test_parse_mcnd_payload_without_jumuah() -> None:
    """MCND publishes no Jumu'ah times today; everything else parses."""
    result = parse_dpt_payload(load_json_fixture("dpt_mcnd.json"), TODAY, DUBLIN, "mcnd-api")
    assert result.jumuah == []
    assert result.iqamah is not None
    assert local(result.today.maghrib) == "18:23"


def test_dict_payload_is_accepted() -> None:
    """A bare dict (not wrapped in a list) is accepted."""
    row = load_json_fixture("dpt_sdic.json")[0]
    result = parse_dpt_payload(row, TODAY, DUBLIN, "sdic-api")
    assert local(result.today.fajr) == row["fajr_begins"][:5]


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ([], "Empty response"),
        ("text", "Unexpected dpt payload"),
        ([{"fajr_begins": "06:00:00"}], "Missing or invalid 'sunrise'"),
    ],
)
def test_bad_payloads_raise(payload: object, match: str) -> None:
    """Unusable payloads raise ValueError (mapped to a provider error upstream)."""
    with pytest.raises((ValueError, TypeError), match=match):
        parse_dpt_payload(payload, TODAY, DUBLIN, "x")
    if isinstance(payload, list) and not payload:
        with pytest.raises(ValueError, match="Empty response"):
            payload_row(payload)


def test_isha_after_midnight_is_moved_to_next_day() -> None:
    """An Isha earlier than Maghrib on the clock belongs to the next day."""
    row = copy.deepcopy(load_json_fixture("dpt_mcnd.json")[0])
    row["maghrib_begins"] = "22:00:00"
    row["isha_begins"] = "00:30:00"
    row.pop("tomorrow")
    result = parse_dpt_payload([row], TODAY, DUBLIN, "x")
    assert result.today.isha > result.today.maghrib
    assert result.today.isha.astimezone(DUBLIN).date() == date(2026, 10, 21)
    assert result.tomorrow is None
    assert result.today.midnight is None
    result.today.validate()


def test_bad_d_date_falls_back_to_target_date() -> None:
    """An unreadable d_date does not break parsing."""
    row = copy.deepcopy(load_json_fixture("dpt_mcnd.json")[0])
    row["d_date"] = "yesterday"
    result = parse_dpt_payload([row], TODAY, DUBLIN, "x")
    assert result.today.fajr.astimezone(DUBLIN).date() == TODAY


def test_payload_date_wins_over_target_date() -> None:
    """When the server is a day behind, rows are labelled with their own date."""
    result = parse_dpt_payload(load_json_fixture("dpt_mcnd.json"), date(2026, 10, 21), DUBLIN, "x")
    assert result.today.fajr.astimezone(DUBLIN).date() == TODAY


def test_unusable_tomorrow_is_ignored() -> None:
    """A broken 'tomorrow' object leaves tomorrow and Midnight unset."""
    row = copy.deepcopy(load_json_fixture("dpt_mcnd.json")[0])
    row["tomorrow"] = {"d_date": "2026-10-21"}
    result = parse_dpt_payload([row], TODAY, DUBLIN, "x")
    assert result.tomorrow is None
    assert result.today.midnight is None


def test_no_jamah_times_gives_no_iqamah() -> None:
    """Rows without any jamah time give iqamah None."""
    row = copy.deepcopy(load_json_fixture("dpt_mcnd.json")[0])
    for key in ("fajr_jamah", "zuhr_jamah", "asr_jamah", "maghrib_jamah", "isha_jamah"):
        row[key] = "00:00:00"
    result = parse_dpt_payload([row], TODAY, DUBLIN, "x")
    assert result.iqamah is None


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {"jumuah": ["13:30", "14:30"], "jumuah_label": ["A", "B"]},
            [("13:30", "A"), ("14:30", "B")],
        ),
        ({"jumuah": ["13:30:00"]}, [("13:30", None)]),
        (
            {"jumuah": ["13:30", "junk", "15:00"], "jumuah_label": ["", "x"]},
            [("13:30", None), ("15:00", None)],
        ),
        ({"jumuah": "13:30"}, []),
        ({}, []),
    ],
)
def test_parse_jumuah(row: dict, expected: list[tuple[str, str | None]]) -> None:
    """Jumu'ah lists are zipped with their labels and junk is skipped."""
    sessions = parse_jumuah(row)
    assert [(s.clock.strftime("%H:%M"), s.label) for s in sessions] == expected
