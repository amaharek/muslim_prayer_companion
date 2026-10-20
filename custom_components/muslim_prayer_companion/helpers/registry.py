"""
Registry of mosques with a known prayer-times source.

The registry is data, not code: ``data/mosques.json`` holds one record per
mosque. Adding a mosque means adding a record (and a translation label), see
CONTRIBUTING.md. The file is read once when this module is imported, which
Home Assistant does in the import executor.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

MOSQUES_PATH = Path(__file__).resolve().parent.parent / "data" / "mosques.json"

SOURCE_TYPE_ICCI_TIMETABLE = "icci_timetable"
SOURCE_TYPE_DPT = "dpt"
SOURCE_TYPE_MAI_HTML = "mai_html"
SOURCE_TYPES = (SOURCE_TYPE_ICCI_TIMETABLE, SOURCE_TYPE_DPT, SOURCE_TYPE_MAI_HTML)
# Source types that need a URL.
URL_SOURCE_TYPES = (SOURCE_TYPE_DPT, SOURCE_TYPE_MAI_HTML)

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class MosqueSource:
    """How a mosque's prayer times are obtained."""

    type: str
    url: str | None = None


@dataclass(frozen=True)
class Mosque:
    """One registry record."""

    key: str
    name: str
    short_name: str
    address: str
    city: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    website: str
    source: MosqueSource
    source_id: str
    jumuah_auto: bool
    credit: str

    @property
    def supports_iqamah(self) -> bool:
        """Return True if the source publishes iqamah (jamah) times."""
        return self.source.type == SOURCE_TYPE_DPT

    @property
    def supports_any_date(self) -> bool:
        """Return True if the source can give times for an arbitrary date."""
        return self.source.type == SOURCE_TYPE_ICCI_TIMETABLE


class RegistryError(ValueError):
    """Raised when the registry file is malformed."""


def _parse_mosque(record: dict[str, Any]) -> Mosque:
    """Build a Mosque from one JSON record, validating every field."""
    try:
        source_raw = record["source"]
        source = MosqueSource(type=source_raw["type"], url=source_raw.get("url"))
        mosque = Mosque(
            key=str(record["key"]),
            name=str(record["name"]),
            short_name=str(record["short_name"]),
            address=str(record["address"]),
            city=str(record["city"]),
            country=str(record["country"]),
            latitude=float(record["latitude"]),
            longitude=float(record["longitude"]),
            timezone=str(record["timezone"]),
            website=str(record["website"]),
            source=source,
            source_id=str(record["source_id"]),
            jumuah_auto=record["jumuah"] == "auto",
            credit=str(record["credit"]),
        )
    except (KeyError, TypeError, ValueError) as err:
        msg = f"invalid mosque record {record.get('key', '?')!r}: {err}"
        raise RegistryError(msg) from err

    if source.type not in SOURCE_TYPES:
        msg = f"mosque {mosque.key!r}: unknown source type {source.type!r}"
        raise RegistryError(msg)
    if source.type in URL_SOURCE_TYPES and not (source.url and source.url.startswith("https://")):
        msg = f"mosque {mosque.key!r}: source type {source.type!r} needs an https URL"
        raise RegistryError(msg)
    if not -90 <= mosque.latitude <= 90 or not -180 <= mosque.longitude <= 180:
        msg = f"mosque {mosque.key!r}: coordinates out of range"
        raise RegistryError(msg)
    if record["jumuah"] not in ("auto", "manual"):
        msg = f"mosque {mosque.key!r}: jumuah must be 'auto' or 'manual'"
        raise RegistryError(msg)
    if mosque.jumuah_auto and source.type != SOURCE_TYPE_DPT:
        msg = f"mosque {mosque.key!r}: only dpt sources publish Jumu'ah times"
        raise RegistryError(msg)
    return mosque


def parse_registry(data: Any) -> dict[str, Mosque]:
    """Parse the registry document into an ordered ``key -> Mosque`` mapping."""
    if not isinstance(data, dict) or not isinstance(data.get("mosques"), list):
        msg = "registry must be an object with a 'mosques' list"
        raise RegistryError(msg)
    mosques: dict[str, Mosque] = {}
    for record in data["mosques"]:
        mosque = _parse_mosque(record)
        if mosque.key in mosques:
            msg = f"duplicate mosque key {mosque.key!r}"
            raise RegistryError(msg)
        mosques[mosque.key] = mosque
    if not mosques:
        msg = "registry has no mosques"
        raise RegistryError(msg)
    return mosques


def load_registry(path: Path = MOSQUES_PATH) -> dict[str, Mosque]:
    """Read and parse the registry file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        msg = f"cannot read mosque registry {path}: {err}"
        raise RegistryError(msg) from err
    return parse_registry(data)


MOSQUES: dict[str, Mosque] = load_registry()
MOSQUE_KEYS: list[str] = list(MOSQUES)


def get_mosque(key: str) -> Mosque:
    """
    Return the registry record for ``key``.

    Raises:
        KeyError: If the key is unknown.
    """
    return MOSQUES[key]


def is_mosque_key(value: str | None) -> bool:
    """Return True if ``value`` names a registered mosque."""
    return value in MOSQUES


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def mosques_by_distance(latitude: float, longitude: float) -> list[tuple[Mosque, float]]:
    """Return every mosque with its distance from a point, nearest first."""
    return sorted(
        (
            (mosque, distance_km(latitude, longitude, mosque.latitude, mosque.longitude))
            for mosque in MOSQUES.values()
        ),
        key=lambda item: item[1],
    )
