"""Diagnostics support for Muslim Prayer Companion."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
import hashlib
import json
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.util import dt as dt_util

from .api_providers.icci_timetable import ICCI_TIMETABLE_PATH
from .helpers.registry import MOSQUES_PATH

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import MuslimPrayerCompanionConfigEntry

TO_REDACT = {"latitude", "longitude", "unique_id", "iqamah_api_url"}


def _serialize(value: Any) -> Any:
    """Make a value JSON friendly (datetimes to ISO strings, recursively)."""
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serialize(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _serialize(dataclasses.asdict(value))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _file_sha256(path: Any) -> str | None:
    """Return the SHA-256 of a bundled data file (run in the executor)."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _timetable_sha256(path: Any) -> str | None:
    """Return the canonical SHA-256 of the bundled timetable's ``timetable`` object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps(data["timetable"], sort_keys=True, separators=(",", ":"))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return hashlib.sha256(canonical.encode()).hexdigest()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MuslimPrayerCompanionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    raw = coordinator.raw_result
    raw_dict = dataclasses.asdict(raw) if raw is not None else None
    if raw_dict is not None:
        raw_dict.pop("raw", None)

    timetable_hash, registry_hash = await hass.async_add_executor_job(
        lambda: (_timetable_sha256(ICCI_TIMETABLE_PATH), _file_sha256(MOSQUES_PATH))
    )

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "settings": async_redact_data(
            _serialize(dataclasses.asdict(coordinator.settings)), TO_REDACT
        ),
        "coordinator": {
            "provider": coordinator.provider_name,
            "source": (coordinator.data or {}).get("source"),
            "fallback_active": coordinator.fallback_active,
            "last_error": coordinator.last_error,
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
            "raw_result": _serialize(raw_dict),
            "data": _serialize(coordinator.data),
        },
        "bundled_data": {
            "icci_timetable_sha256": timetable_hash,
            "mosque_registry_sha256": registry_hash,
        },
        "now": dt_util.utcnow().isoformat(),
        "time_zone": hass.config.time_zone,
    }
