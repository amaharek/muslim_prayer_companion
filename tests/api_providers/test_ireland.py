"""Test cases for Ireland API providers."""

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.muslim_prayer_companion.api_providers.base import (
    ProviderConfig,
    ProviderConnectionError,
    ProviderResponseError,
)
from custom_components.muslim_prayer_companion.api_providers.ireland import (
    IRELAND_APIS,
    IrelandProvider,
)


class TestIrelandProviderInit:
    """Test Ireland provider initialization."""

    def test_valid_api_key_accepted(self):
        """Valid Ireland API keys should be accepted."""
        for api_key in ["ie-icci", "ie-mcnd", "ie-hicc", "ie-sdic"]:
            config = ProviderConfig(
                latitude=53.0,
                longitude=-6.0,
                calculation_method=api_key,
                timezone="Europe/Dublin",
            )
            provider = IrelandProvider(config)
            assert provider.api_name is not None

    def test_invalid_api_key_raises(self):
        """Invalid API key should raise ValueError."""
        config = ProviderConfig(
            latitude=53.0,
            longitude=-6.0,
            calculation_method="ie-invalid",
            timezone="Europe/Dublin",
        )

        with pytest.raises(ValueError, match="Unknown Ireland API"):
            IrelandProvider(config)

    def test_mosque_info_available(self):
        """Provider should have mosque info."""
        config = ProviderConfig(
            latitude=53.0,
            longitude=-6.0,
            calculation_method="ie-icci",
            timezone="Europe/Dublin",
        )
        provider = IrelandProvider(config)

        mosque = provider.mosque_info
        assert mosque.name == "Islamic Cultural Centre of Ireland"
        assert mosque.uuid == "ie-icci"
        assert mosque.city == "Dublin"


class TestIrelandProviderICCI:
    """Test ICCI API response parsing."""

    @pytest.fixture
    def icci_provider(self) -> IrelandProvider:
        """Create ICCI provider."""
        config = ProviderConfig(
            latitude=53.2663,
            longitude=-6.2135,
            calculation_method="ie-icci",
            timezone="Europe/Dublin",
        )
        return IrelandProvider(config)

    def test_parse_icci_response_valid(
        self, icci_provider: IrelandProvider, icci_api_response: dict[str, Any]
    ):
        """Valid ICCI response should be parsed correctly."""
        target_date = date(2024, 1, 1)
        result = icci_provider._parse_icci_response(icci_api_response, target_date)

        # Validate parsed data
        result.validate()

        # Check times are reasonable
        assert result.fajr.hour == 6
        assert result.fajr.minute == 45
        assert result.dhuhr.hour == 12
        assert result.dhuhr.minute == 30

    def test_parse_icci_response_missing_day_raises(
        self, icci_provider: IrelandProvider
    ):
        """Missing day in response should raise ValueError."""
        response = {"timetable": {"1": {}}}  # No days
        target_date = date(2024, 1, 15)

        with pytest.raises(ValueError, match="No prayer times found"):
            icci_provider._parse_icci_response(response, target_date)

    def test_parse_icci_response_incomplete_times_raises(
        self, icci_provider: IrelandProvider
    ):
        """Incomplete prayer times should raise ValueError."""
        response = {
            "timetable": {
                "1": {
                    "1": [[6, 45], [8, 30]],  # Only 2 times, need 6
                }
            }
        }
        target_date = date(2024, 1, 1)

        with pytest.raises(ValueError, match="Incomplete prayer times"):
            icci_provider._parse_icci_response(response, target_date)


class TestIrelandProviderWordPress:
    """Test WordPress-based API response parsing (MCND, HICC, SDIC)."""

    @pytest.fixture
    def mcnd_provider(self) -> IrelandProvider:
        """Create MCND provider."""
        config = ProviderConfig(
            latitude=53.4023,
            longitude=-6.1756,
            calculation_method="ie-mcnd",
            timezone="Europe/Dublin",
        )
        return IrelandProvider(config)

    def test_parse_wordpress_response_valid(
        self,
        mcnd_provider: IrelandProvider,
        wordpress_api_response: list[dict[str, Any]],
    ):
        """Valid WordPress response should be parsed correctly."""
        target_date = date(2024, 1, 1)
        result = mcnd_provider._parse_wordpress_response(
            wordpress_api_response, target_date
        )

        # Validate parsed data
        result.validate()

        # Check times
        assert result.fajr.hour == 6
        assert result.fajr.minute == 45
        assert result.dhuhr.hour == 12
        assert result.dhuhr.minute == 30

    def test_parse_wordpress_response_empty_raises(
        self, mcnd_provider: IrelandProvider
    ):
        """Empty response should raise ValueError."""
        with pytest.raises(ValueError, match="Empty response"):
            mcnd_provider._parse_wordpress_response([], date.today())

    def test_parse_wordpress_iqamah_times(
        self,
        mcnd_provider: IrelandProvider,
        wordpress_api_response: list[dict[str, Any]],
    ):
        """WordPress response should include iqamah times."""
        target_date = date(2024, 1, 1)
        result = mcnd_provider._parse_wordpress_iqamah(
            wordpress_api_response, target_date
        )

        # Check iqamah times
        assert result.fajr is not None
        assert result.fajr.hour == 7
        assert result.fajr.minute == 0

        assert result.juma is not None
        assert result.juma.hour == 13
        assert result.juma.minute == 30

    def test_wordpress_provider_supports_iqamah(self, mcnd_provider: IrelandProvider):
        """WordPress-based providers should support iqamah times."""
        assert mcnd_provider.supports_iqamah is True

    def test_icci_provider_does_not_support_iqamah(self):
        """ICCI provider should not support iqamah times."""
        config = ProviderConfig(
            latitude=53.0,
            longitude=-6.0,
            calculation_method="ie-icci",
            timezone="Europe/Dublin",
        )
        provider = IrelandProvider(config)
        assert provider.supports_iqamah is False


class TestIrelandProviderAllAPIs:
    """Test that all Ireland APIs return same format."""

    @pytest.mark.parametrize("api_key", ["ie-icci", "ie-mcnd", "ie-hicc", "ie-sdic"])
    def test_all_apis_have_mosque_info(self, api_key: str):
        """All Ireland APIs should have mosque info defined."""
        assert api_key in IRELAND_APIS
        assert "mosque_info" in IRELAND_APIS[api_key]

        mosque = IRELAND_APIS[api_key]["mosque_info"]
        assert mosque.name is not None
        assert mosque.uuid == api_key
        assert mosque.latitude is not None
        assert mosque.longitude is not None

    @pytest.mark.parametrize("api_key", ["ie-icci", "ie-mcnd", "ie-hicc", "ie-sdic"])
    def test_all_apis_have_valid_url(self, api_key: str):
        """All Ireland APIs should have valid URLs."""
        assert "url" in IRELAND_APIS[api_key]
        url = IRELAND_APIS[api_key]["url"]
        assert url.startswith("https://")

    @pytest.mark.parametrize("api_key", ["ie-mcnd", "ie-hicc", "ie-sdic"])
    def test_wordpress_apis_marked_correctly(self, api_key: str):
        """WordPress-based APIs should be marked as 'wordpress' type."""
        assert IRELAND_APIS[api_key]["type"] == "wordpress"

    def test_icci_api_marked_correctly(self):
        """ICCI API should be marked as 'icci' type."""
        assert IRELAND_APIS["ie-icci"]["type"] == "icci"


class TestIrelandProviderMosqueSearch:
    """Test mosque search functionality."""

    @pytest.mark.asyncio
    async def test_search_mosques_returns_all_ireland_mosques(self):
        """search_mosques should return all Ireland mosques."""
        config = ProviderConfig(
            latitude=53.0,
            longitude=-6.0,
            calculation_method="ie-icci",
            timezone="Europe/Dublin",
        )
        provider = IrelandProvider(config)

        mosques = await provider.async_search_mosques(53.0, -6.0)

        assert len(mosques) == 4
        uuids = [m.uuid for m in mosques]
        assert "ie-icci" in uuids
        assert "ie-mcnd" in uuids
        assert "ie-hicc" in uuids
        assert "ie-sdic" in uuids

    def test_supports_mosque_search(self):
        """Ireland provider should support mosque search."""
        config = ProviderConfig(
            latitude=53.0,
            longitude=-6.0,
            calculation_method="ie-icci",
            timezone="Europe/Dublin",
        )
        provider = IrelandProvider(config)
        assert provider.supports_mosque_search is True
