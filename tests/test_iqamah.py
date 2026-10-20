"""Tests for the iqamah helpers and the custom iqamah API client."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.muslim_prayer_companion.helpers.iqamah import (
    IqamahApiClient,
    iqamah_from_offsets,
    parse_iqamah_json,
)

DUBLIN = ZoneInfo("Europe/Dublin")
TODAY = date(2026, 10, 20)
URL = "https://example.ie/iqamah.json"


def test_iqamah_from_offsets() -> None:
    """Offsets are added to each present prayer only."""
    fajr = datetime(2026, 10, 20, 5, 16, tzinfo=UTC)
    result = iqamah_from_offsets({"Fajr": fajr, "Sunrise": fajr}, {"Fajr": 20, "Dhuhr": 15})
    assert result == {"Fajr": fajr + timedelta(minutes=20)}


@pytest.mark.parametrize(
    "payload",
    [
        {"Fajr": "06:30", "Dhuhr": "13:30", "Asr": "16:00", "Maghrib": "18:30", "Isha": "20:15"},
        {"fajr": "06:30:00", "dhuhr": "13:30", "asr": "16:00", "maghrib": "18:30", "isha": "20:15"},
        {
            "iqamah": {
                "Fajr": "06:30",
                "Dhuhr": "13:30",
                "Asr": "16:00",
                "Maghrib": "18:30",
                "Isha": "20:15",
            }
        },
        [
            {
                "fajr_jamah": "06:30:00",
                "zuhr_jamah": "13:30:00",
                "asr_jamah": "16:00:00",
                "maghrib_jamah": "18:30:00",
                "isha_jamah": "20:15:00",
            }
        ],
    ],
)
def test_parse_iqamah_json_shapes(payload: object) -> None:
    """Prayer-name dicts, dpt jamah keys, nested and list-wrapped payloads all parse."""
    data = parse_iqamah_json(payload, TODAY, DUBLIN)
    assert data.fajr == datetime(2026, 10, 20, 5, 30, tzinfo=UTC)
    assert data.isha == datetime(2026, 10, 20, 19, 15, tzinfo=UTC)


def test_parse_iqamah_json_partial_and_bad() -> None:
    """Missing prayers are None; no prayers at all is an error."""
    data = parse_iqamah_json({"Fajr": "06:30"}, TODAY, DUBLIN)
    assert data.fajr is not None
    assert data.dhuhr is None
    with pytest.raises(ValueError, match="no iqamah times"):
        parse_iqamah_json({"foo": "bar"}, TODAY, DUBLIN)
    with pytest.raises(ValueError, match="empty"):
        parse_iqamah_json([], TODAY, DUBLIN)
    with pytest.raises(TypeError, match="unexpected"):
        parse_iqamah_json("text", TODAY, DUBLIN)


async def test_api_client_keeps_last_good_and_warns_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """The client returns fresh data, keeps today's last good value on failure, warns once."""
    session = aioclient_mock.create_session(hass.loop)
    client = IqamahApiClient(session, URL, DUBLIN)

    aioclient_mock.get(URL, json={"Fajr": "06:30"})
    first = await client.async_fetch(TODAY)
    assert first is not None
    assert first.fajr == datetime(2026, 10, 20, 5, 30, tzinfo=UTC)

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, status=500)
    with caplog.at_level(logging.WARNING):
        assert await client.async_fetch(TODAY) == first
        assert await client.async_fetch(TODAY) == first
        assert await client.async_fetch(TODAY + timedelta(days=1)) is None
    assert len([r for r in caplog.records if "Could not fetch iqamah" in r.getMessage()]) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, text="<html>nope</html>")
    assert await client.async_fetch(TODAY) == first  # not JSON: still a failure

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json={"Dhuhr": "13:30"})
    with caplog.at_level(logging.INFO):
        fresh = await client.async_fetch(TODAY)
    assert fresh is not None
    assert fresh.dhuhr is not None
    assert "available again" in caplog.text
    await session.close()
