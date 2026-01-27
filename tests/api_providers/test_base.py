"""Test cases for base API provider classes and data models."""

from datetime import date, datetime, timedelta, timezone

import pytest

from custom_components.muslim_prayer_companion.api_providers.base import (
    IqamahTimesData,
    MosqueInfo,
    PrayerTimesData,
    ProviderConfig,
)


class TestPrayerTimesData:
    """Test PrayerTimesData validation and conversion."""

    def test_valid_prayer_times_pass_validation(
        self, sample_prayer_times: PrayerTimesData
    ):
        """Valid prayer times should pass validation."""
        # Should not raise
        sample_prayer_times.validate()

    def test_prayer_times_out_of_order_fails(self):
        """Prayer times out of chronological order should fail validation."""
        base_date = date.today()
        data = PrayerTimesData(
            fajr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                5,
                30,
                tzinfo=timezone.utc,
            ),
            sunrise=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                4,
                0,
                tzinfo=timezone.utc,
            ),  # Before fajr!
            dhuhr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                12,
                30,
                tzinfo=timezone.utc,
            ),
            asr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                15,
                45,
                tzinfo=timezone.utc,
            ),
            maghrib=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                18,
                30,
                tzinfo=timezone.utc,
            ),
            isha=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                20,
                0,
                tzinfo=timezone.utc,
            ),
        )

        with pytest.raises(AssertionError, match="out of order"):
            data.validate()

    def test_naive_datetime_rejected(self):
        """Timezone-naive datetimes should fail validation."""
        base_date = date.today()
        data = PrayerTimesData(
            fajr=datetime(
                base_date.year, base_date.month, base_date.day, 5, 30
            ),  # No timezone!
            sunrise=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                7,
                15,
                tzinfo=timezone.utc,
            ),
            dhuhr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                12,
                30,
                tzinfo=timezone.utc,
            ),
            asr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                15,
                45,
                tzinfo=timezone.utc,
            ),
            maghrib=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                18,
                30,
                tzinfo=timezone.utc,
            ),
            isha=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                20,
                0,
                tzinfo=timezone.utc,
            ),
        )

        with pytest.raises(AssertionError, match="timezone-aware"):
            data.validate()

    def test_imsak_after_fajr_fails(self):
        """Imsak time after Fajr should fail validation."""
        base_date = date.today()
        data = PrayerTimesData(
            fajr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                5,
                30,
                tzinfo=timezone.utc,
            ),
            sunrise=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                7,
                15,
                tzinfo=timezone.utc,
            ),
            dhuhr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                12,
                30,
                tzinfo=timezone.utc,
            ),
            asr=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                15,
                45,
                tzinfo=timezone.utc,
            ),
            maghrib=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                18,
                30,
                tzinfo=timezone.utc,
            ),
            isha=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                20,
                0,
                tzinfo=timezone.utc,
            ),
            imsak=datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                6,
                0,
                tzinfo=timezone.utc,
            ),  # After fajr!
        )

        with pytest.raises(AssertionError, match="Imsak.*before Fajr"):
            data.validate()

    def test_to_dict_returns_ha_compatible_keys(
        self, sample_prayer_times: PrayerTimesData
    ):
        """to_dict should return Home Assistant compatible keys."""
        result = sample_prayer_times.to_dict()

        # Check required keys exist
        assert "Fajr" in result
        assert "Sunrise" in result
        assert "Dhuhr" in result
        assert "Asr" in result
        assert "Maghrib" in result
        assert "Isha" in result
        assert "Sunset" in result

        # Values should be datetime objects
        for key, value in result.items():
            assert isinstance(value, datetime)
            assert value.tzinfo is not None


class TestIqamahTimesData:
    """Test IqamahTimesData validation and conversion."""

    def test_valid_iqamah_times_pass_validation(
        self, sample_iqamah_times: IqamahTimesData
    ):
        """Valid iqamah times should pass validation."""
        sample_iqamah_times.validate()

    def test_naive_iqamah_datetime_rejected(self):
        """Timezone-naive iqamah times should fail validation."""
        base_date = date.today()
        data = IqamahTimesData(
            fajr=datetime(
                base_date.year, base_date.month, base_date.day, 5, 50
            ),  # No timezone!
        )

        with pytest.raises(AssertionError, match="timezone-aware"):
            data.validate()

    def test_to_dict_uses_correct_key_format(
        self, sample_iqamah_times: IqamahTimesData
    ):
        """to_dict should use iqamah_ prefix for keys."""
        result = sample_iqamah_times.to_dict()

        # Keys should have iqamah_ prefix
        assert "iqamah_Fajr" in result
        assert "iqamah_Dhuhr" in result
        assert "iqamah_Asr" in result
        assert "iqamah_Maghrib" in result
        assert "iqamah_Isha" in result

    def test_to_dict_omits_none_values(self):
        """to_dict should omit None values."""
        data = IqamahTimesData(
            fajr=datetime(2024, 1, 1, 5, 50, tzinfo=timezone.utc),
            # Others are None
        )
        result = data.to_dict()

        assert "iqamah_Fajr" in result
        assert "iqamah_Dhuhr" not in result
        assert "iqamah_Asr" not in result


class TestMosqueInfo:
    """Test MosqueInfo dataclass."""

    def test_mosque_info_creation(self):
        """Test creating MosqueInfo with all fields."""
        mosque = MosqueInfo(
            name="Test Mosque",
            uuid="test-123",
            latitude=53.3498,
            longitude=-6.2603,
            address="123 Test St",
            city="Dublin",
            country="Ireland",
            website="https://example.com",
            timezone="Europe/Dublin",
        )

        assert mosque.name == "Test Mosque"
        assert mosque.uuid == "test-123"
        assert mosque.latitude == 53.3498
        assert mosque.longitude == -6.2603
        assert mosque.city == "Dublin"

    def test_mosque_info_optional_fields(self):
        """Test MosqueInfo with only required fields."""
        mosque = MosqueInfo(
            name="Minimal Mosque",
            uuid="min-123",
            latitude=53.0,
            longitude=-6.0,
        )

        assert mosque.address is None
        assert mosque.city is None
        assert mosque.country is None


class TestProviderConfig:
    """Test ProviderConfig dataclass."""

    def test_provider_config_creation(self, provider_config: ProviderConfig):
        """Test creating ProviderConfig."""
        assert provider_config.latitude == 53.3498
        assert provider_config.longitude == -6.2603
        assert provider_config.calculation_method == "isna"
        assert provider_config.timezone == "Europe/Dublin"
        assert provider_config.mosque_id is None
        assert provider_config.api_key is None

    def test_provider_config_with_optional_fields(self):
        """Test ProviderConfig with optional fields."""
        config = ProviderConfig(
            latitude=53.0,
            longitude=-6.0,
            calculation_method="ie-icci",
            timezone="Europe/Dublin",
            mosque_id="mosque-123",
            api_key="secret-key",
        )

        assert config.mosque_id == "mosque-123"
        assert config.api_key == "secret-key"
