"""Packaging consistency: manifest.json, pyproject.toml and hacs.json."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).parent.parent
MANIFEST = ROOT / "custom_components" / "muslim_prayer_companion" / "manifest.json"

HACS_ALLOWED_KEYS = {
    "name",
    "content_in_root",
    "country",
    "filename",
    "hacs",
    "hide_default_branch",
    "homeassistant",
    "persistent_directory",
    "render_readme",
    "zip_release",
}


def test_manifest_requirements_match_pyproject() -> None:
    """Runtime requirements are pinned and identical in both files."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["requirements"] == pyproject["project"]["dependencies"]
    for requirement in manifest["requirements"]:
        assert "==" in requirement, requirement
    assert manifest["version"] == pyproject["project"]["version"]


def test_manifest_fields() -> None:
    """hassfest-relevant fields."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["domain"] == "muslim_prayer_companion"
    assert manifest["iot_class"] == "calculated"
    assert manifest["integration_type"] == "service"
    assert manifest["config_flow"] is True
    assert "icon" not in manifest
    assert list(manifest)[:2] == ["domain", "name"]
    assert list(manifest)[2:] == sorted(manifest)[0:0] + sorted(list(manifest)[2:])


def test_hacs_json_schema() -> None:
    """hacs.json only uses keys HACS accepts."""
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert set(hacs) <= HACS_ALLOWED_KEYS
    assert hacs["zip_release"] is True
    assert hacs["filename"] == "muslim_prayer_companion.zip"
    assert hacs["render_readme"] is True
