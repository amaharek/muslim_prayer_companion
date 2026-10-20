"""Consistency of strings.json and the translation files with the code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from custom_components.muslim_prayer_companion import SERVICE_SCHEMA
from custom_components.muslim_prayer_companion.const import (
    COUNTDOWN_FORMATS,
    IQAMAH_METHODS,
    ISSUE_PROVIDER_FALLBACK,
    SENSOR_GROUPS,
    SERVICE_GET_PRAYER_TIMES,
    SOURCE_TYPES,
    STANDARD_CALC_METHODS,
)
from custom_components.muslim_prayer_companion.helpers import friday
from custom_components.muslim_prayer_companion.helpers.registry import MOSQUE_KEYS

COMPONENT = Path(__file__).parent.parent / "custom_components" / "muslim_prayer_companion"


def _load(name: str) -> dict:
    return json.loads((COMPONENT / name).read_text(encoding="utf-8"))


def _keys(data: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        if isinstance(value, dict):
            keys |= _keys(value, f"{prefix}{key}.")
        else:
            keys.add(f"{prefix}{key}")
    return keys


def test_strings_mirror_english() -> None:
    """strings.json is byte-identical to translations/en.json."""
    assert (COMPONENT / "strings.json").read_text(encoding="utf-8") == (
        COMPONENT / "translations" / "en.json"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("language", ["ar"])
def test_translations_have_the_same_keys(language: str) -> None:
    """Every language covers exactly the English keys."""
    assert _keys(_load(f"translations/{language}.json")) == _keys(_load("translations/en.json"))


def test_selector_options_match_constants() -> None:
    """Selector option labels exist for every value the code offers."""
    selectors = _load("strings.json")["selector"]
    assert set(selectors["source_type"]["options"]) == set(SOURCE_TYPES)
    assert set(selectors["ireland_mosque"]["options"]) == set(MOSQUE_KEYS)
    assert set(selectors["friday_source"]["options"]) == {"manual", *MOSQUE_KEYS}
    assert set(selectors["calculation_method"]["options"]) == set(STANDARD_CALC_METHODS)
    assert set(selectors["iqamah_method"]["options"]) == set(IQAMAH_METHODS)
    assert set(selectors["countdown_format"]["options"]) == set(COUNTDOWN_FORMATS)
    assert set(selectors["sensor_groups"]["options"]) == set(SENSOR_GROUPS)


def test_option_errors_and_menus_are_translated() -> None:
    """Every error key the flows can return has a message; menus list their steps."""
    options = _load("strings.json")["options"]
    error_keys = {getattr(friday, name) for name in dir(friday) if name.startswith("ERROR_")} | {
        "invalid_url",
        "url_required",
    }
    assert error_keys <= set(options["error"])
    assert set(options["step"]["init"]["menu_options"]) == {
        "method",
        "iqamah",
        "friday",
        "hijri",
        "display",
    }
    assert set(options["step"]["friday"]["menu_options"]) == {
        "friday_add",
        "friday_select",
        "friday_remove",
        "init",
    }
    for step in (
        "method",
        "iqamah",
        "friday_add",
        "friday_select",
        "friday_edit",
        "friday_remove",
        "hijri",
        "display",
    ):
        assert step in options["step"]


def test_issue_and_exceptions_and_services() -> None:
    """Repairs issue, exception messages and the action are described."""
    strings = _load("strings.json")
    issue = strings["issues"][ISSUE_PROVIDER_FALLBACK]
    for placeholder in ("{location}", "{mosque}", "{url}", "{error}", "{fallback}"):
        assert placeholder in issue["title"] + issue["description"]
    assert set(strings["exceptions"]) == {"date_not_available", "entry_not_found", "no_entries"}

    service = strings["services"][SERVICE_GET_PRAYER_TIMES]
    services_yaml = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))
    yaml_fields = set(services_yaml[SERVICE_GET_PRAYER_TIMES]["fields"])
    assert set(service["fields"]) == yaml_fields
    schema_fields = {str(key) for key in SERVICE_SCHEMA.schema}
    assert yaml_fields == schema_fields
