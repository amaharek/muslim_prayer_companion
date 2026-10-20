"""
Shared fixtures for Muslim Prayer Companion tests.

Tests run against the real Home Assistant test harness (``hass`` fixture and
``MockConfigEntry``). Home Assistant is placed in Dublin, Irish local time.
Network access is blocked by pytest-socket; the mosque APIs are served from
``tests/fixtures`` through ``aioclient_mock``.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from prayer_times_calculator_offline.praytimes import PrayTimes
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.muslim_prayer_companion.api_providers.base import (
    IqamahTimesData,
    PrayerTimesData,
    ProviderConfig,
)
from custom_components.muslim_prayer_companion.api_providers.icci_timetable import (
    load_icci_timetable,
)
from custom_components.muslim_prayer_companion.const import (
    CONF_CALC_METHOD,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    CONFIG_VERSION,
    DOMAIN,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
)
from custom_components.muslim_prayer_companion.helpers.registry import get_mosque
from custom_components.muslim_prayer_companion.helpers.settings import (
    default_options,
    entry_unique_id,
)

FIXTURES = Path(__file__).parent / "fixtures"

DUBLIN_LAT = 53.3498
DUBLIN_LON = -6.2603

MCND_URL = get_mosque("ie-mcnd").source.url
HICC_URL = get_mosque("ie-hicc").source.url
SDIC_URL = get_mosque("ie-sdic").source.url
MAI_URL = get_mosque("ie-mai").source.url

# A Tuesday in Irish summer time: 12:00 in Dublin.
FROZEN_NOW = "2026-10-20 11:00:00+00:00"


def load_fixture(name: str) -> str:
    """Return the text of ``tests/fixtures/<name>``."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json_fixture(name: str) -> Any:
    """Return the parsed JSON of ``tests/fixtures/<name>``."""
    return json.loads(load_fixture(name))


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components/ in every test."""


@pytest.fixture(autouse=True)
async def _dublin(hass: HomeAssistant) -> None:
    """Run Home Assistant in Dublin, Irish local time."""
    await hass.config.async_set_time_zone("Europe/Dublin")
    hass.config.latitude = DUBLIN_LAT
    hass.config.longitude = DUBLIN_LON


@pytest.fixture(autouse=True)
def _clear_timetable_cache() -> Generator[None]:
    """Make every test load the bundled ICCI timetable again."""
    load_icci_timetable.cache_clear()
    yield
    load_icci_timetable.cache_clear()


@pytest.fixture(autouse=True)
def _offline_calculator_accepts_fake_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Let prayer-times-calculator-offline work while freezegun is active.

    ``PrayTimes.getTimes`` recognises a date only when ``type(date).__name__``
    is ``"date"``; freezegun's fake date class fails that check and the
    library crashes. Production code is unaffected, so the shim lives here.
    """
    original = PrayTimes.getTimes

    def get_times(self: PrayTimes, when: Any, *args: Any, **kwargs: Any) -> Any:
        if hasattr(when, "year"):
            when = (when.year, when.month, when.day)
        return original(self, when, *args, **kwargs)

    monkeypatch.setattr(PrayTimes, "getTimes", get_times)


@pytest.fixture
def provider_config() -> ProviderConfig:
    """A calculated provider configuration for Dublin."""
    return ProviderConfig(
        latitude=DUBLIN_LAT,
        longitude=DUBLIN_LON,
        calculation_method="isna",
        timezone="Europe/Dublin",
    )


@pytest.fixture
def sample_prayer_times() -> PrayerTimesData:
    """Sample prayer times (UTC) for the data-model tests."""
    day = datetime(2026, 10, 20, tzinfo=UTC)
    return PrayerTimesData(
        fajr=day.replace(hour=5, minute=30),
        sunrise=day.replace(hour=7, minute=15),
        dhuhr=day.replace(hour=12, minute=30),
        asr=day.replace(hour=15, minute=45),
        maghrib=day.replace(hour=18, minute=30),
        isha=day.replace(hour=20, minute=0),
        midnight=day.replace(hour=23, minute=59),
    )


@pytest.fixture
def sample_iqamah_times() -> IqamahTimesData:
    """Sample iqamah times (UTC) for the data-model tests."""
    day = datetime(2026, 10, 20, tzinfo=UTC)
    return IqamahTimesData(
        fajr=day.replace(hour=5, minute=50),
        dhuhr=day.replace(hour=12, minute=45),
        asr=day.replace(hour=16, minute=0),
        maghrib=day.replace(hour=18, minute=40),
        isha=day.replace(hour=20, minute=15),
    )


def make_entry(
    source: str = SOURCE_CALCULATED,
    method: str = "isna",
    *,
    latitude: float = DUBLIN_LAT,
    longitude: float = DUBLIN_LON,
    name: str = "Dublin",
    options: dict[str, Any] | None = None,
    version: int = CONFIG_VERSION,
    unique_id: str | None = "auto",
) -> MockConfigEntry:
    """Return a version-3 config entry for a calculated location or an Irish mosque."""
    if source == SOURCE_IRELAND:
        mosque = get_mosque(method)
        latitude, longitude = mosque.latitude, mosque.longitude
        name = mosque.short_name
        timezone = mosque.timezone
    else:
        timezone = "Europe/Dublin"
    data = {
        CONF_SOURCE_TYPE: source,
        CONF_CALC_METHOD: method,
        CONF_LATITUDE: latitude,
        CONF_LONGITUDE: longitude,
        CONF_LOCATION_NAME: name,
        CONF_TIMEZONE: timezone,
    }
    entry_options = default_options(source, method)
    if options:
        entry_options.update(options)
    if unique_id == "auto":
        unique_id = entry_unique_id(source, method, latitude, longitude)
    return MockConfigEntry(
        domain=DOMAIN,
        version=version,
        title=name,
        unique_id=unique_id,
        data=data,
        options=entry_options,
    )


@pytest.fixture
def calculated_entry() -> MockConfigEntry:
    """A calculated (ISNA) entry for Dublin."""
    return make_entry()


@pytest.fixture
def icci_entry() -> MockConfigEntry:
    """An entry for the Islamic Cultural Centre of Ireland (bundled timetable)."""
    return make_entry(SOURCE_IRELAND, "ie-icci")


@pytest.fixture
def mcnd_entry() -> MockConfigEntry:
    """An entry for Muslim Community North Dublin (WordPress dpt API)."""
    return make_entry(SOURCE_IRELAND, "ie-mcnd")


@pytest.fixture
def hicc_entry() -> MockConfigEntry:
    """An entry for Hansfield Islamic Cultural Centre (dpt API with Jumu'ah times)."""
    return make_entry(SOURCE_IRELAND, "ie-hicc")


@pytest.fixture
def mai_entry() -> MockConfigEntry:
    """An entry for the Muslim Association of Ireland, Tallaght (homepage scrape)."""
    return make_entry(SOURCE_IRELAND, "ie-mai")


@pytest.fixture
def mock_mosque_sites(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Serve every mosque site from the fixtures captured on 20 Oct 2026."""
    aioclient_mock.get(MCND_URL, json=load_json_fixture("dpt_mcnd.json"))
    aioclient_mock.get(HICC_URL, json=load_json_fixture("dpt_hicc.json"))
    aioclient_mock.get(SDIC_URL, json=load_json_fixture("dpt_sdic.json"))
    aioclient_mock.get(MAI_URL, text=load_fixture("mai_home.html"))
    return aioclient_mock


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add the entry and run the full setup (first refresh and sensor platform)."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta) -> None:
    """
    Move the clock forward, fire due timers and wait for every resulting task.

    The coordinator's interval refresh runs as a background task, which a plain
    ``async_block_till_done()`` would not wait for.
    """
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def move_to(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: str) -> None:
    """Jump the clock to ``when`` (ISO string), fire due timers and wait."""
    freezer.move_to(when)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def entity_id_for(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """Return the entity_id of the sensor with data key ``key`` for ``entry``."""
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{key}_{entry.entry_id}")
    assert entity_id is not None, f"no sensor for {key}"
    return entity_id


def state_of(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> Any:
    """Return the state object of the sensor with data key ``key``."""
    state = hass.states.get(entity_id_for(hass, entry, key))
    assert state is not None
    return state
