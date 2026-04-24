"""Pydantic models for the Eagleshot API."""

import re

from pydantic import BaseModel, Field, field_validator, model_validator

from utils import parse_iso_timestamp, iso_utc


class AppConfig(BaseModel):
    """Configuration for a camera station.
    
    Camera schedule notes:
    - camera_start_time and camera_stop_time must be in HH:MM (24-hour) format
    - camera_start_time must be strictly earlier than camera_stop_time
    - When use_sunrise_sunset is True, the start/stop times are ignored by the
      device and sunrise/sunset times are used instead. The start/stop time values
      may still be stored but are not operationally used.
    - capture_interval_minutes must be between 1 and 1440 (minutes in a day)
    - description is limited to 500 characters
    """
    camera_start_time: str = Field(default="06:00")
    camera_stop_time: str = Field(default="20:00")
    use_sunrise_sunset: bool = False
    capture_interval_minutes: int = Field(default=30, ge=1, le=1440)
    title: str = ""
    description: str = Field(default="", max_length=500)
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    location: str = ""
    country: str = ""
    country_emoji: str = ""
    is_online: bool | None = None
    last_online: str | None = None
    next_online: str | None = None

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
        """Validate that camera start time is before stop time."""
        if self.camera_start_time >= self.camera_stop_time:
            raise ValueError(
                f"Camera start time ({self.camera_start_time}) must be earlier than stop time ({self.camera_stop_time})"
            )
        return self


class LoginRequest(BaseModel):
    """Request payload for login endpoint."""
    username: str
    password: str


class AuthResponse(BaseModel):
    """Response from login endpoint."""
    expires_in: int
    username: str


class MeResponse(BaseModel):
    """Response from /auth/me endpoint."""
    username: str


class ChartDataSource(BaseModel):
    """Selectable chart data source stored in the station database."""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    icon: str = Field(min_length=1)
    color: str = Field(min_length=1)

    @field_validator("id", "label", "icon", "color")
    @classmethod
    def validate_chart_text_field(cls, value: str) -> str:
        return value.strip()
