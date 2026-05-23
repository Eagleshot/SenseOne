"""Tests for Pydantic models."""

import pytest

from models import AppConfig, LoginRequest, AuthResponse, MeResponse


class TestAppConfig:
    """Test AppConfig model validation."""

    def test_app_config_defaults(self):
        """Test AppConfig with defaults."""
        config = AppConfig()
        assert config.station_start_time == "06:00"
        assert config.station_stop_time == "20:00"
        assert config.capture_interval_minutes == 30
        assert config.use_sunrise_sunset is False

    def test_app_config_with_values(self):
        """Test AppConfig with custom values."""
        config = AppConfig(
            title="Test Station",
            station_start_time="07:00",
            station_stop_time="19:00",
            capture_interval_minutes=60,
        )
        assert config.title == "Test Station"
        assert config.station_start_time == "07:00"
        assert config.capture_interval_minutes == 60

    def test_old_camera_schedule_fields_are_rejected(self):
        """The public config contract is stationStartTime/stationStopTime only."""
        with pytest.raises(ValueError):
            AppConfig(cameraStartTime="07:00", cameraStopTime="19:00")

    def test_invalid_time_format(self):
        """Test that invalid time format is rejected."""
        with pytest.raises(ValueError, match="HH:MM"):
            AppConfig(station_start_time="6:00")  # Missing leading zero
        
        with pytest.raises(ValueError, match="HH:MM"):
            AppConfig(station_start_time="25:00")  # Invalid hour

    def test_invalid_time_order(self):
        """Test that start time must be before stop time."""
        with pytest.raises(ValueError, match="earlier than"):
            AppConfig(
                station_start_time="20:00",
                station_stop_time="06:00",
            )

    def test_same_start_stop_time_rejected(self):
        """Test that same start and stop times are rejected."""
        with pytest.raises(ValueError, match="earlier than"):
            AppConfig(
                station_start_time="12:00",
                station_stop_time="12:00",
            )

    def test_capture_interval_bounds(self):
        """Test capture interval validation."""
        # Too small
        with pytest.raises(ValueError):
            AppConfig(capture_interval_minutes=0)
        
        # Too large
        with pytest.raises(ValueError):
            AppConfig(capture_interval_minutes=1441)
        
        # Valid boundaries
        config1 = AppConfig(capture_interval_minutes=1)
        assert config1.capture_interval_minutes == 1
        
        config2 = AppConfig(capture_interval_minutes=1440)
        assert config2.capture_interval_minutes == 1440

    def test_description_length_limit(self):
        """Test description length limiting."""
        # Valid
        config = AppConfig(description="a" * 500)
        assert len(config.description) == 500
        
        # Too long
        with pytest.raises(ValueError):
            AppConfig(description="a" * 501)

    def test_text_field_stripping(self):
        """Test that text fields are stripped."""
        config = AppConfig(
            title="  Test  ",
            location="  Location  ",
        )
        assert config.title == "Test"
        assert config.location == "Location"

    def test_timestamp_validation(self):
        """Test timestamp field validation."""
        # Valid ISO timestamp
        config = AppConfig(last_online="2024-01-01T12:30:00Z")
        assert config.last_online == "2024-01-01T12:30:00Z"
        
        # Invalid timestamp
        with pytest.raises(ValueError, match="ISO 8601"):
            AppConfig(last_online="invalid")

    def test_optional_timestamp_fields(self):
        """Test that timestamp fields are optional."""
        config = AppConfig(last_online=None, next_online=None)
        assert config.last_online is None
        assert config.next_online is None

class TestLoginRequest:
    """Test LoginRequest model."""

    def test_login_request_required_fields(self):
        """Test that username and password are required."""
        with pytest.raises(ValueError):
            LoginRequest(username="test")  # Missing password


class TestAuthResponse:
    """Test AuthResponse model."""

    def test_auth_response_structure(self):
        """Test AuthResponse structure."""
        response = AuthResponse(expires_in=3600, username="testuser")
        assert response.expires_in == 3600
        assert response.username == "testuser"


class TestMeResponse:
    """Test MeResponse model."""

    def test_me_response_structure(self):
        """Test MeResponse structure."""
        response = MeResponse(username="testuser")
        assert response.username == "testuser"




