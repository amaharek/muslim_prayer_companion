"""Typed view of a config entry's data and options, with defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..const import (
    CONF_CALC_METHOD,
    CONF_COUNTDOWN_FORMAT,
    CONF_ENABLED_GROUPS,
    CONF_FRIDAY_MOSQUES,
    CONF_HIJRI_ADJUSTMENT,
    CONF_HIJRI_CHANGE_AT_MAGHRIB,
    CONF_IMSAK_MINUTES,
    CONF_IQAMAH_API_URL,
    CONF_IQAMAH_METHOD,
    CONF_IQAMAH_OFFSETS,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_PRAYER_WINDOW_MINUTES,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    COUNTDOWN_FORMATS,
    DEFAULT_CALC_METHOD,
    DEFAULT_COUNTDOWN_FORMAT,
    DEFAULT_HIJRI_ADJUSTMENT,
    DEFAULT_HIJRI_CHANGE_AT_MAGHRIB,
    DEFAULT_IMSAK_MINUTES,
    DEFAULT_IQAMAH_METHOD,
    DEFAULT_IQAMAH_OFFSETS,
    DEFAULT_LOCATION_NAME,
    DEFAULT_PRAYER_WINDOW_MINUTES,
    DEFAULT_SOURCE_TYPE,
    IQAMAH_METHOD_API,
    IQAMAH_METHOD_MOSQUE,
    IQAMAH_METHODS,
    MAX_HIJRI_ADJUSTMENT,
    MIN_HIJRI_ADJUSTMENT,
    PRAYERS,
    SENSOR_GROUPS,
    SOURCE_IRELAND,
    STANDARD_CALC_METHODS,
)
from .friday import FridayMosqueConfig, friday_configs, seed_friday_mosques
from .registry import get_mosque, is_mosque_key

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry


def mosque_key_from(data: Mapping[str, Any]) -> str | None:
    """Return the registry key of an Irish entry, or None for calculated entries."""
    if data.get(CONF_SOURCE_TYPE) != SOURCE_IRELAND:
        return None
    key = data.get(CONF_CALC_METHOD)
    return key if is_mosque_key(key) else None


def entry_unique_id(source_type: str, method: str, latitude: float, longitude: float) -> str:
    """Return the config entry unique_id: one entry per mosque, or per location."""
    if source_type == SOURCE_IRELAND:
        return f"ireland:{method}"
    return f"calculated:{float(latitude):.4f},{float(longitude):.4f}"


def default_iqamah_method(mosque_key: str | None) -> str:
    """Mosques that publish jamah times default to them; everyone else to offsets."""
    if mosque_key and is_mosque_key(mosque_key) and get_mosque(mosque_key).supports_iqamah:
        return IQAMAH_METHOD_MOSQUE
    return DEFAULT_IQAMAH_METHOD


def default_options(source_type: str, method: str) -> dict[str, Any]:
    """Return the full options dict for a new entry."""
    mosque_key = method if source_type == SOURCE_IRELAND else None
    options: dict[str, Any] = {
        CONF_IQAMAH_METHOD: default_iqamah_method(mosque_key),
        CONF_IQAMAH_OFFSETS: dict(DEFAULT_IQAMAH_OFFSETS),
        CONF_IQAMAH_API_URL: None,
        CONF_FRIDAY_MOSQUES: seed_friday_mosques(mosque_key),
        CONF_HIJRI_ADJUSTMENT: DEFAULT_HIJRI_ADJUSTMENT,
        CONF_HIJRI_CHANGE_AT_MAGHRIB: DEFAULT_HIJRI_CHANGE_AT_MAGHRIB,
        CONF_IMSAK_MINUTES: DEFAULT_IMSAK_MINUTES,
        CONF_ENABLED_GROUPS: list(SENSOR_GROUPS),
        CONF_COUNTDOWN_FORMAT: DEFAULT_COUNTDOWN_FORMAT,
        CONF_PRAYER_WINDOW_MINUTES: DEFAULT_PRAYER_WINDOW_MINUTES,
    }
    if source_type != SOURCE_IRELAND:
        options[CONF_CALC_METHOD] = method
    return options


def _int_option(options: Mapping[str, Any], key: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(options.get(key, default))
    except (TypeError, ValueError):
        return default
    return min(max(value, lo), hi)


@dataclass(frozen=True)
class Settings:
    """Everything the coordinator and the platforms need from an entry."""

    source_type: str
    calc_method: str
    mosque_key: str | None
    latitude: float
    longitude: float
    location_name: str
    timezone: str
    iqamah_method: str
    iqamah_offsets: dict[str, int]
    iqamah_api_url: str | None
    friday_mosques: list[FridayMosqueConfig]
    hijri_adjustment: int
    hijri_change_at_maghrib: bool
    imsak_minutes: int
    enabled_groups: frozenset[str]
    countdown_format: str
    prayer_window_minutes: int

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> Settings:
        """Read an entry's data and options, filling defaults for anything missing."""
        return cls.from_mappings(entry.data, entry.options)

    @classmethod
    def from_mappings(cls, data: Mapping[str, Any], options: Mapping[str, Any]) -> Settings:
        """Build settings from raw data/options mappings."""
        source_type = data.get(CONF_SOURCE_TYPE, DEFAULT_SOURCE_TYPE)
        mosque_key = mosque_key_from(data)
        if source_type == SOURCE_IRELAND:
            calc_method = str(data.get(CONF_CALC_METHOD, ""))
        else:
            calc_method = str(
                options.get(CONF_CALC_METHOD, data.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD))
            )
            if calc_method not in STANDARD_CALC_METHODS:
                calc_method = DEFAULT_CALC_METHOD

        iqamah_method = options.get(CONF_IQAMAH_METHOD, default_iqamah_method(mosque_key))
        if iqamah_method not in IQAMAH_METHODS:
            iqamah_method = DEFAULT_IQAMAH_METHOD
        raw_offsets = options.get(CONF_IQAMAH_OFFSETS) or {}
        offsets = {
            prayer: _int_option(raw_offsets, prayer, DEFAULT_IQAMAH_OFFSETS[prayer], 0, 24 * 60)
            for prayer in PRAYERS
        }
        api_url = options.get(CONF_IQAMAH_API_URL) or None
        if iqamah_method == IQAMAH_METHOD_API and not api_url:
            iqamah_method = DEFAULT_IQAMAH_METHOD

        groups_raw = options.get(CONF_ENABLED_GROUPS)
        enabled_groups = (
            frozenset(g for g in groups_raw if g in SENSOR_GROUPS)
            if isinstance(groups_raw, list)
            else frozenset(SENSOR_GROUPS)
        )
        countdown_format = options.get(CONF_COUNTDOWN_FORMAT, DEFAULT_COUNTDOWN_FORMAT)
        if countdown_format not in COUNTDOWN_FORMATS:
            countdown_format = DEFAULT_COUNTDOWN_FORMAT

        return cls(
            source_type=source_type,
            calc_method=calc_method,
            mosque_key=mosque_key,
            latitude=float(data.get(CONF_LATITUDE, 0.0)),
            longitude=float(data.get(CONF_LONGITUDE, 0.0)),
            location_name=str(data.get(CONF_LOCATION_NAME) or DEFAULT_LOCATION_NAME),
            timezone=str(data.get(CONF_TIMEZONE) or "UTC"),
            iqamah_method=iqamah_method,
            iqamah_offsets=offsets,
            iqamah_api_url=api_url,
            friday_mosques=friday_configs(options.get(CONF_FRIDAY_MOSQUES)),
            hijri_adjustment=_int_option(
                options,
                CONF_HIJRI_ADJUSTMENT,
                DEFAULT_HIJRI_ADJUSTMENT,
                MIN_HIJRI_ADJUSTMENT,
                MAX_HIJRI_ADJUSTMENT,
            ),
            hijri_change_at_maghrib=bool(
                options.get(CONF_HIJRI_CHANGE_AT_MAGHRIB, DEFAULT_HIJRI_CHANGE_AT_MAGHRIB)
            ),
            imsak_minutes=_int_option(options, CONF_IMSAK_MINUTES, DEFAULT_IMSAK_MINUTES, 0, 60),
            enabled_groups=enabled_groups,
            countdown_format=countdown_format,
            prayer_window_minutes=_int_option(
                options, CONF_PRAYER_WINDOW_MINUTES, DEFAULT_PRAYER_WINDOW_MINUTES, 0, 24 * 60
            ),
        )

    @property
    def is_ireland(self) -> bool:
        """Return True for an Irish mosque entry."""
        return self.source_type == SOURCE_IRELAND and self.mosque_key is not None
