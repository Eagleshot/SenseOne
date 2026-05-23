"""Pydantic models for the Eagleshot API."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from utils import parse_iso_timestamp, iso_utc


def to_camel(value: str) -> str:
    """Convert a snake_case field name to the public camelCase API name."""
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class ApiModel(BaseModel):
    """Base model for public API schemas."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AppConfig(ApiModel):
    """Persisted configuration document for a camera station.

    Schedule fields drive when the device captures images. When
    `useSunriseSunset` is true, the device computes start/stop from the
    station's lat/lon and the stored start/stop values are ignored
    operationally (but kept in the document so the UI can show them).
    """
    camera_start_time: str = Field(
        default="06:00",
        description="Earliest time of day the device may capture, in HH:MM 24-hour format.",
    )
    camera_stop_time: str = Field(
        default="20:00",
        description="Latest time of day the device may capture, in HH:MM 24-hour format.",
    )
    use_sunrise_sunset: bool = Field(
        default=False,
        description=(
            "When true, the device uses local sunrise/sunset times derived from "
            "lat/lon and ignores the start/stop fields above."
        ),
    )
    capture_interval_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Minutes between captures during the active window (1 to 1440).",
    )
    title: str = Field(default="", description="Human-readable station title shown in the UI.")
    description: str = Field(
        default="",
        max_length=500,
        description="Free-form description shown on the station detail page. Up to 500 chars.",
    )
    lat: float = Field(default=0.0, description="Latitude in decimal degrees (-90 to 90).")
    lon: float = Field(default=0.0, description="Longitude in decimal degrees (-180 to 180).")
    alt: float = Field(default=0.0, description="Altitude in metres above sea level.")
    location: str = Field(default="", description="Place name shown in the UI (e.g. valley or peak).")
    country: str = Field(default="", description="ISO country name in plain text.")
    country_emoji: str = Field(
        default="",
        description="Optional flag emoji shown next to the country name.",
    )
    is_public: bool = Field(
        default=True,
        description="When false, the station is hidden from anonymous and non-owner callers.",
    )
    last_online: str | None = Field(
        default=None,
        description="ISO 8601 timestamp of the most recent successful device contact.",
    )
    next_online: str | None = Field(
        default=None,
        description="ISO 8601 timestamp the device is expected to check in next, if known.",
    )

    @field_validator("camera_start_time", "camera_stop_time")
    @classmethod
    def validate_time_field(cls, value: str) -> str:
        candidate = value.strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", candidate):
            raise ValueError("Time must be in HH:MM (24-hour) format.")
        return candidate

    @field_validator("title", "description", "location", "country", "country_emoji")
    @classmethod
    def validate_text_field(cls, value: str) -> str:
        return value.strip()

    @field_validator("last_online", "next_online")
    @classmethod
    def validate_timestamp_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = parse_iso_timestamp(value)
        if parsed is None:
            raise ValueError("Timestamp must be ISO 8601.")
        return iso_utc(parsed)

    @model_validator(mode="after")
    def validate_times_order(self) -> "AppConfig":
        """Validate that camera start time is before stop time.

        Skipped when use_sunrise_sunset is enabled, since the device ignores
        start/stop times in that mode and the stored values may be stale.
        """
        if self.use_sunrise_sunset:
            return self
        if self.camera_start_time >= self.camera_stop_time:
            raise ValueError(
                f"Camera start time ({self.camera_start_time}) must be earlier than stop time ({self.camera_stop_time})"
            )
        return self


class LoginRequest(ApiModel):
    """Credentials posted to POST /v1/auth/login."""
    username: str = Field(description="Account username, case-sensitive.")
    password: str = Field(description="Account password in plaintext (over HTTPS).")


class AuthResponse(ApiModel):
    """Returned by POST /v1/auth/login on success."""
    expires_in: int = Field(
        description="Seconds until the session cookie / token expires.",
    )
    username: str = Field(description="Username of the now-authenticated account.")
    is_admin: bool = Field(
        default=False,
        description="True if the account has admin privileges.",
    )


class MeResponse(ApiModel):
    """Returned by GET /v1/auth/me for the currently-logged-in user."""
    username: str = Field(description="Username of the authenticated session.")
    is_admin: bool = Field(
        default=False,
        description="True if the account has admin privileges.",
    )


class StationDeviceSecretResponse(ApiModel):
    """One-time payload returned when rotating a station's device HMAC secret.

    The secret is shown exactly once. Flash it to the device and discard the
    response — the server keeps the same value in its protected meta file
    for verification, but the API will never reveal it again.
    """
    station_id: str = Field(description="Station the secret belongs to.")
    device_hmac_secret: str = Field(
        description=(
            "Base64url-encoded (no padding) 32-byte secret. Use it as the HMAC "
            "key for signing device requests against this station."
        ),
    )


class StationCoordinates(ApiModel):
    """Station coordinates exposed by metadata endpoints."""
    lat: float = Field(description="Latitude in decimal degrees.")
    lng: float = Field(description="Longitude in decimal degrees.")
    altitude: float = Field(description="Altitude in metres above sea level.")


class StationSummaryResponse(ApiModel):
    """Lightweight per-station row returned by list endpoints."""
    id: str = Field(description="Stable station identifier used in URLs.")
    name: str = Field(description="Display name for the station.")
    location: str = Field(description="Place name shown in the UI (e.g. valley or peak).")
    country: str = Field(default="", description="ISO country name in plain text.")
    country_emoji: str = Field(default="", description="Optional flag emoji.")
    coordinates: StationCoordinates = Field(description="Lat/lng/altitude bundle.")
    is_public: bool = Field(
        default=True,
        description="True when anonymous callers can see the station.",
    )
    is_online: bool = Field(
        description="True when the device has checked in recently enough to count as online.",
    )


class StationDetailResponse(StationSummaryResponse):
    """Detail row returned for a single station — superset of the summary."""
    description: str = Field(default="", description="Free-form station description.")
    battery: int | None = Field(default=None, description="Most recent battery reading (0-100), if known.")
    current_image: str | None = Field(default=None, description="URL of the most recent stored image.")
    last_update: str | None = Field(default=None, description="ISO 8601 timestamp of last device contact.")
    next_update: str | None = Field(default=None, description="ISO 8601 timestamp of expected next contact.")


class TimelineItemResponse(ApiModel):
    """One entry in a station's image-capture timeline."""
    timestamp: str = Field(description="ISO 8601 capture timestamp, UTC.")
    url: str = Field(description="URL to fetch the image (relative to the API origin).")


class ImageUploadResponse(ApiModel):
    """Returned after a device upload is successfully stored."""

    filename: str = Field(description="Server-assigned filename (includes a timestamp prefix).")
    url: str = Field(description="URL where the just-uploaded image can be fetched.")


class SensorHistoryResponse(ApiModel):
    """One sensor-history row (units in metric)."""
    timestamp: str = Field(description="ISO 8601 reading timestamp, UTC.")
    temperature: float = Field(description="Air temperature in degrees Celsius.")
    humidity: int = Field(description="Relative humidity in percent (0-100).")
    pressure: int = Field(description="Atmospheric pressure in hPa.")
    battery: int = Field(description="Battery level in percent (0-100).")
    wind_speed: float = Field(description="Wind speed in m/s.")
    wind_direction: int = Field(description="Wind direction in degrees, 0=N clockwise.")
    visibility: float = Field(description="Visibility in km.")
    uv_index: int = Field(description="UV index (0+).")
    dew_point: float = Field(description="Dew point in degrees Celsius.")
    feels_like: float = Field(description="Apparent ('feels like') temperature in degrees Celsius.")


class SensorReadingRequest(ApiModel):
    """One sensor reading submitted by a device. Same units as SensorHistoryResponse."""

    timestamp: str | None = Field(
        default=None,
        description=(
            "Optional ISO 8601 timestamp. When omitted, the server stamps the "
            "row with the current UTC time on receipt."
        ),
    )
    temperature: float = Field(description="Air temperature in degrees Celsius.")
    humidity: int = Field(ge=0, le=100, description="Relative humidity in percent (0-100).")
    pressure: int = Field(gt=0, description="Atmospheric pressure in hPa.")
    battery: int = Field(ge=0, le=100, description="Battery level in percent (0-100).")
    wind_speed: float = Field(
        ge=0,
        description="Wind speed in m/s.",
    )
    wind_direction: int = Field(
        ge=0,
        le=360,
        description="Wind direction in degrees, 0=N clockwise.",
    )
    visibility: float = Field(ge=0, description="Visibility in km.")
    uv_index: int = Field(
        ge=0,
        description="UV index (0+).",
    )
    dew_point: float = Field(
        description="Dew point in degrees Celsius.",
    )
    feels_like: float = Field(
        description="Apparent ('feels like') temperature in degrees Celsius.",
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = parse_iso_timestamp(value)
        if parsed is None:
            raise ValueError("Timestamp must be ISO 8601.")
        return iso_utc(parsed)


