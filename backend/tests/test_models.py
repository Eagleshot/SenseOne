"""Tests for Pydantic models."""

import pytest

from models import AppConfig, LoginRequest, AuthResponse, MeResponse, SensorReadingRequest


class TestSensorReadingMetricKeys:
    """Metric keys become datastream rows and chart titles — charset is enforced."""

    def test_valid_metric_keys_accepted(self):
        request = SensorReadingRequest.model_validate(
            {"readings": [{"temperature": 1.5, "wind_speed.avg-1": 2}]}
        )
        assert request.readings[0].metrics == {"temperature": 1.5, "wind_speed.avg-1": 2}

    def test_metric_key_with_forbidden_characters_rejected(self):
        for bad_key in ("wind speed", "temp‮e", "temp\x00", "uv!"):
            with pytest.raises(ValueError, match="letters, digits"):
                SensorReadingRequest.model_validate({"readings": [{bad_key: 1}]})


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

    def test_out_of_range_coordinates_rejected(self):
        """lat/lon are bounded like StationCreateRequest, so PUT /config can't store junk."""
        with pytest.raises(ValueError):
            AppConfig(lat=90.1)
        with pytest.raises(ValueError):
            AppConfig(lat=-90.1)
        with pytest.raises(ValueError):
            AppConfig(lon=180.1)
        with pytest.raises(ValueError):
            AppConfig(lon=-180.1)

    def test_non_finite_and_out_of_range_altitude_rejected(self):
        """A stored inf/nan would break JSON serialization of every station response."""
        with pytest.raises(ValueError):
            AppConfig(alt=float("inf"))
        with pytest.raises(ValueError):
            AppConfig(alt=float("nan"))
        with pytest.raises(ValueError):
            AppConfig.model_validate_json('{"alt": 1e999}')  # parses to inf
        with pytest.raises(ValueError):
            AppConfig(alt=9001)
        with pytest.raises(ValueError):
            AppConfig(alt=-501)
        assert AppConfig(alt=4478.0).alt == 4478.0

    def test_text_fields_have_length_limits(self):
        """PUT /config must not accept multi-megabyte titles."""
        with pytest.raises(ValueError):
            AppConfig(title="x" * 121)
        with pytest.raises(ValueError):
            AppConfig(location="x" * 161)
        with pytest.raises(ValueError):
            AppConfig(country="x" * 81)
        assert AppConfig(title="x" * 120).title == "x" * 120

    def test_control_and_bidi_characters_stripped(self):
        """Control chars and bidi overrides are UI-spoofing vectors; strip them."""
        config = AppConfig(
            title="Sta‮tion\x00",
            description="line one\nline two\x07",
            location="Davos⁦",
        )
        assert config.title == "Station"
        assert config.description == "line one\nline two"  # newlines survive
        assert config.location == "Davos"

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
        """Test that email and password are required."""
        with pytest.raises(ValueError):
            LoginRequest(email="test@example.com")  # Missing password

    def test_login_request_rejects_invalid_email(self):
        """A malformed email is rejected."""
        with pytest.raises(ValueError):
            LoginRequest(email="not-an-email", password="whatever12345")

    def test_login_request_normalizes_email(self):
        """Email is lower-cased and trimmed."""
        request = LoginRequest(email="  Admin@Example.COM ", password="whatever12345")
        assert request.email == "admin@example.com"


class TestAuthResponse:
    """Test AuthResponse model."""

    def test_auth_response_structure(self):
        """Test AuthResponse structure."""
        response = AuthResponse(expires_in=3600, email="testuser@example.com")
        assert response.expires_in == 3600
        assert response.email == "testuser@example.com"


class TestMeResponse:
    """Test MeResponse model."""

    def test_me_response_structure(self):
        """Test MeResponse structure."""
        response = MeResponse(email="testuser@example.com")
        assert response.email == "testuser@example.com"




