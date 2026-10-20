"""Tests for the offline calculated provider."""

from __future__ import annotations

from datetime import UTC, date, datetime
import logging
from zoneinfo import ZoneInfo

import pytest

from custom_components.muslim_prayer_companion.api_providers.base import (
    ProviderConfig,
    ProviderResponseError,
)
from custom_components.muslim_prayer_companion.api_providers.calculated import (
    CalculatedProvider,
    parse_calculated_time,
    parse_calculated_times,
)
from custom_components.muslim_prayer_companion.const import STANDARD_CALC_METHODS

DUBLIN = ZoneInfo("Europe/Dublin")
ICCI = ProviderConfig(
    latitude=53.2663, longitude=-6.2135, calculation_method="isna", timezone="Europe/Dublin"
)


async def test_fetch_today_and_tomorrow() -> None:
    """One fetch gives today and tomorrow, in UTC, with Midnight after Maghrib."""
    provider = CalculatedProvider(ICCI)
    result = await provider.async_fetch(date(2026, 10, 20))

    assert result.source == "calculated:isna"
    assert provider.fallback_source_id == "calculated-fallback:isna"
    assert result.today.maghrib == datetime(2026, 10, 20, 17, 18, tzinfo=UTC)
    assert result.today.fajr == datetime(2026, 10, 20, 5, 25, tzinfo=UTC)
    assert result.today.midnight is not None
    assert result.today.midnight > result.today.maghrib
    assert result.today.sunset == result.today.maghrib
    result.today.validate()

    assert result.tomorrow is not None
    assert result.tomorrow.fajr.astimezone(DUBLIN).date() == date(2026, 10, 21)
    result.tomorrow.validate()
    assert provider.supports_any_date is True
    assert provider.supports_iqamah is False


async def test_fetch_single_day() -> None:
    """The single-day method still works."""
    data = await CalculatedProvider(ICCI).async_fetch_prayer_times(date(2026, 6, 21))
    assert data.maghrib.astimezone(DUBLIN).strftime("%H:%M") == "21:56"


def test_unknown_method_defaults_to_isna(caplog: pytest.LogCaptureFixture) -> None:
    """An unknown method logs a warning and falls back to ISNA."""
    with caplog.at_level(logging.WARNING):
        provider = CalculatedProvider(
            ProviderConfig(latitude=53.0, longitude=-6.0, calculation_method="nope", timezone="UTC")
        )
    assert provider.method == "isna"
    assert "Unknown calculation method" in caplog.text


def test_unknown_timezone_uses_utc(caplog: pytest.LogCaptureFixture) -> None:
    """An unknown zone is reported and UTC used."""
    with caplog.at_level(logging.WARNING):
        CalculatedProvider(
            ProviderConfig(
                latitude=53.0, longitude=-6.0, calculation_method="isna", timezone="Mars/Olympus"
            )
        )
    assert "Unknown time zone" in caplog.text


@pytest.mark.parametrize("method", STANDARD_CALC_METHODS)
async def test_every_method_calculates(method: str) -> None:
    """Every offered method works for Dublin on a summer day."""
    provider = CalculatedProvider(
        ProviderConfig(
            latitude=53.35, longitude=-6.26, calculation_method=method, timezone="Europe/Dublin"
        )
    )
    result = await provider.async_fetch(date(2026, 6, 21))
    result.today.validate()


async def test_high_latitude_summer_validates() -> None:
    """Helsinki at midsummer still gives ordered times (Fajr before local midnight in UTC)."""
    provider = CalculatedProvider(
        ProviderConfig(
            latitude=60.17, longitude=24.94, calculation_method="isna", timezone="Europe/Helsinki"
        )
    )
    result = await provider.async_fetch(date(2026, 6, 21))
    result.today.validate()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-20T06:16:00+01:00", datetime(2026, 10, 20, 5, 16, tzinfo=UTC)),
        ("2026-10-20T05:16:00+00:00", datetime(2026, 10, 20, 5, 16, tzinfo=UTC)),
        ("06:16", datetime(2026, 10, 20, 5, 16, tzinfo=UTC)),
        ("2026-10-20T06:16:00", datetime(2026, 10, 20, 5, 16, tzinfo=UTC)),
    ],
)
def test_parse_calculated_time(value: str, expected: datetime) -> None:
    """ISO strings with offsets, naive ISO strings and bare HH:MM are all understood."""
    assert parse_calculated_time(value, date(2026, 10, 20), DUBLIN) == expected


@pytest.mark.parametrize("value", ["", None, "junk", 42])
def test_parse_calculated_time_rejects_junk(value: object) -> None:
    """Anything else raises ValueError."""
    with pytest.raises(ValueError):
        parse_calculated_time(value, date(2026, 10, 20), DUBLIN)


def test_parse_times_moves_isha_and_midnight_after_maghrib() -> None:
    """Bare clock times for Isha/Midnight earlier than Maghrib belong to the next day."""
    raw = {
        "Fajr": "03:00",
        "Sunrise": "04:30",
        "Dhuhr": "13:00",
        "Asr": "17:00",
        "Maghrib": "22:30",
        "Isha": "00:15",
        "Midnight": "01:00",
    }
    data = parse_calculated_times(raw, date(2026, 6, 21), DUBLIN, "calculated:isna")
    assert data.isha > data.maghrib
    assert data.midnight is not None
    assert data.midnight > data.isha
    data.validate()


async def test_calculation_error_is_a_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Library failures surface as ProviderResponseError."""
    provider = CalculatedProvider(ICCI)
    monkeypatch.setattr(provider, "_calculate", lambda _day: {"Fajr": "junk"})
    with pytest.raises(ProviderResponseError, match="Invalid prayer times format"):
        await provider.async_fetch_prayer_times(date(2026, 10, 20))

    def boom(*_args: object) -> dict:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(provider, "_calculate_days", boom)
    with pytest.raises(ProviderResponseError, match="boom"):
        await provider.async_fetch(date(2026, 10, 20))
