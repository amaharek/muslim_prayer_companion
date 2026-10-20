"""Tests for the mosque registry (data/mosques.json)."""

from __future__ import annotations

import copy
import json

import pytest

from custom_components.muslim_prayer_companion.helpers import registry
from custom_components.muslim_prayer_companion.helpers.registry import (
    MOSQUE_KEYS,
    MOSQUES,
    RegistryError,
    distance_km,
    get_mosque,
    is_mosque_key,
    mosques_by_distance,
    parse_registry,
)

from .conftest import FIXTURES

TRANSLATIONS = (
    FIXTURES.parent.parent / "custom_components" / "muslim_prayer_companion" / "translations"
)

VALID_RECORD = {
    "key": "ie-test",
    "name": "Test Mosque",
    "short_name": "TEST",
    "address": "1 Test Road",
    "city": "Dublin",
    "country": "Ireland",
    "latitude": 53.3,
    "longitude": -6.3,
    "timezone": "Europe/Dublin",
    "website": "https://example.ie",
    "source": {"type": "dpt", "url": "https://example.ie/wp-json/dpt/v1/prayertime?filter=today"},
    "source_id": "test-api",
    "jumuah": "auto",
    "credit": "Test",
}


def test_registry_has_the_five_irish_mosques() -> None:
    """The shipped registry lists ICCI, MCND, HICC, SDIC and MAI."""
    assert MOSQUE_KEYS == ["ie-icci", "ie-mcnd", "ie-hicc", "ie-sdic", "ie-mai"]
    assert get_mosque("ie-icci").source.type == "icci_timetable"
    assert get_mosque("ie-mai").source.type == "mai_html"
    for key in ("ie-mcnd", "ie-hicc", "ie-sdic"):
        assert get_mosque(key).source.type == "dpt"
        assert get_mosque(key).jumuah_auto is True
        assert get_mosque(key).supports_iqamah is True
    assert get_mosque("ie-icci").supports_any_date is True
    assert is_mosque_key("ie-icci") is True
    assert is_mosque_key("isna") is False
    assert is_mosque_key(None) is False


def test_every_mosque_is_in_ireland() -> None:
    """Coordinates and time zone are plausible for Ireland."""
    for mosque in MOSQUES.values():
        assert 51.0 <= mosque.latitude <= 55.5
        assert -11.0 <= mosque.longitude <= -5.5
        assert mosque.timezone == "Europe/Dublin"
        assert mosque.website.startswith("https://")


@pytest.mark.parametrize("language", ["en", "ar"])
def test_every_mosque_has_translated_labels(language: str) -> None:
    """Each registry key has a label in the mosque and Friday-source selectors."""
    translations = json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
    for key in MOSQUE_KEYS:
        assert key in translations["selector"]["ireland_mosque"]["options"]
        assert key in translations["selector"]["friday_source"]["options"]


def test_parse_valid_record() -> None:
    """A complete record parses."""
    mosques = parse_registry({"mosques": [VALID_RECORD]})
    assert mosques["ie-test"].source.url is not None
    assert mosques["ie-test"].jumuah_auto is True


def _with(**changes: object) -> dict:
    record = copy.deepcopy(VALID_RECORD)
    for key, value in changes.items():
        if key == "source_type":
            record["source"]["type"] = value
        elif key == "source_url":
            record["source"]["url"] = value
        else:
            record[key] = value
    return record


@pytest.mark.parametrize(
    ("record", "match"),
    [
        (_with(source_type="unknown"), "unknown source type"),
        (_with(source_url="http://insecure.ie/x"), "needs an https URL"),
        (_with(source_url=None), "needs an https URL"),
        (_with(latitude=95.0), "coordinates out of range"),
        (_with(jumuah="sometimes"), "jumuah must be"),
        (_with(source_type="icci_timetable", jumuah="auto"), "only dpt sources"),
        ({k: v for k, v in VALID_RECORD.items() if k != "name"}, "invalid mosque record"),
    ],
)
def test_parse_rejects_bad_records(record: dict, match: str) -> None:
    """Malformed records are rejected with a clear message."""
    with pytest.raises(RegistryError, match=match):
        parse_registry({"mosques": [record]})


def test_parse_rejects_duplicates_and_empty() -> None:
    """Keys must be unique and the list non-empty."""
    with pytest.raises(RegistryError, match="duplicate"):
        parse_registry({"mosques": [VALID_RECORD, VALID_RECORD]})
    with pytest.raises(RegistryError, match="no mosques"):
        parse_registry({"mosques": []})
    with pytest.raises(RegistryError, match="must be an object"):
        parse_registry([VALID_RECORD])


def test_load_registry_missing_file(tmp_path: object) -> None:
    """A missing file is reported as a registry error."""
    with pytest.raises(RegistryError, match="cannot read"):
        registry.load_registry(tmp_path / "nope.json")  # type: ignore[operator]


def test_mosques_by_distance() -> None:
    """Nearest mosque first; the mosque itself is at distance zero."""
    icci = get_mosque("ie-icci")
    ordered = mosques_by_distance(icci.latitude, icci.longitude)
    assert ordered[0][0].key == "ie-icci"
    assert ordered[0][1] == pytest.approx(0.0)
    distances = [km for _, km in ordered]
    assert distances == sorted(distances)


def test_distance_km() -> None:
    """Dublin to Cork is roughly 220 km."""
    assert distance_km(53.3498, -6.2603, 51.8985, -8.4756) == pytest.approx(220, abs=10)
