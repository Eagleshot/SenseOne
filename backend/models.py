"""Pydantic models for the Eagleshot API."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from metrics_registry import DEFAULT_CHANNEL, METRICS, RESERVED_READING_KEYS
from utils import parse_iso_timestamp, iso_utc


def to_camel(value: str) -> str:
    """Convert a snake_case field name to the public camelCase API name."""
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class ApiModel(BaseModel):
    """Base model for public API schemas."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class AppConfig(ApiModel):
    """Persisted configuration document for a station.

    Schedule fields drive when the device captures images. When
    `useSunriseSunset` is true, the device computes start/stop from the
    station's lat/lon and the stored start/stop values are ignored
    operationally (but kept in the document so the UI can show them).
    """
    station_start_time: str = Field(
        default="06:00",
        description="Earliest time of day the device may capture, in HH:MM 24-hour format.",
    )
    station_stop_time: str = Field(
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

    @field_validator("station_start_time", "station_stop_time")
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
        """Validate that station start time is before stop time.

        Skipped when use_sunrise_sunset is enabled, since the device ignores
        start/stop times in that mode and the stored values may be stale.
        """
        if self.use_sunrise_sunset:
            return self
        if self.station_start_time >= self.station_stop_time:
            raise ValueError(
                f"Station start time ({self.station_start_time}) must be earlier than stop time ({self.station_stop_time})"
            )
        return self


class DeviceConfig(ApiModel):
    """Trimmed config sent to a device, derived from the station's AppConfig.

    Carries only what the device needs (and may need): the capture schedule plus
    lat/lon/alt for possible device-side sunrise/sunset computation. Start/stop are
    expressed as integer minutes since midnight so the firmware does no string parsing.
    """
    station_start_minute: int = Field(
        description="Earliest minute-of-day the device may capture (0 to 1439)."
    )
    station_stop_minute: int = Field(
        description="Latest minute-of-day the device may capture (0 to 1439)."
    )
    use_sunrise_sunset: bool = Field(
        description="When true, the device derives the active window from lat/lon."
    )
    capture_interval_minutes: int = Field(
        description="Minutes between captures during the active window."
    )
    lat: float = Field(description="Latitude in decimal degrees.")
    lon: float = Field(description="Longitude in decimal degrees.")
    alt: float = Field(description="Altitude in metres above sea level.")
    name: str = Field(
        description=(
            "Filename-safe ASCII station name token (umlauts transliterated, e.g. "
            "'Zuerich'). The device uses it to name capture files "
            "'YYYYMMDD_HHMMZ_<name>.jpg' so its local copy matches the dashboard download."
        )
    )


class LoginRequest(ApiModel):
    """Credentials posted to POST /auth/login."""
    email: str = Field(description="User email address; the login identity.")
    password: str = Field(description="User password in plaintext (over HTTPS).")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned):
            raise ValueError("A valid email address is required.")
        return cleaned


class AuthResponse(ApiModel):
    """Returned by POST /auth/login on success."""
    expires_in: int = Field(
        description="Seconds until the session cookie / token expires.",
    )
    email: str = Field(description="Email of the now-authenticated user.")
    is_admin: bool = Field(
        default=False,
        description="True if the user has admin privileges.",
    )


class MeResponse(ApiModel):
    """Returned by GET /auth/me for the currently-logged-in user."""
    email: str = Field(description="Email of the authenticated session.")
    is_admin: bool = Field(
        default=False,
        description="True if the user has admin privileges.",
    )


class StationCreateRequest(ApiModel):
    """Payload for creating a new owned station."""
    title: str = Field(min_length=1, max_length=120, description="Human-readable station title shown in the UI.")
    location: str = Field(default="", max_length=160, description="Place name shown in the UI.")
    country: str = Field(default="", max_length=80, description="Country name shown in the UI.")
    country_emoji: str = Field(default="", max_length=16, description="Optional flag emoji or short marker.")
    lat: float = Field(default=0.0, ge=-90, le=90, description="Latitude in decimal degrees.")
    lon: float = Field(default=0.0, ge=-180, le=180, description="Longitude in decimal degrees.")
    alt: float = Field(default=0.0, description="Altitude in metres above sea level.")
    is_public: bool = Field(default=False, description="Whether anonymous visitors can see the station.")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title must not be blank.")
        return cleaned

    @field_validator("location", "country", "country_emoji")
    @classmethod
    def validate_text_field(cls, value: str) -> str:
        return value.strip()


class StationDeviceSecretResponse(ApiModel):
    """One-time payload returned when rotating a station's device HMAC secret.

    The secret is shown exactly once. Flash it to the device and discard the
    response — the server keeps the same value (encrypted at rest, in the
    station_device_secrets table) for verification, but the API will never
    reveal it again.
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
    id: str = Field(description="Opaque, stable station identifier used in API calls and device signing.")
    url_slug: str = Field(description="Editable, human-friendly slug for the public page URL.")
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
    can_edit: bool = Field(
        default=False,
        description="True when the authenticated caller may edit this station (owner or admin).",
    )


class StationDetailResponse(StationSummaryResponse):
    """Detail row returned for a single station — superset of the summary."""
    description: str = Field(default="", description="Free-form station description.")
    battery: int | None = Field(default=None, description="Most recent battery reading (0-100), if known.")
    current_image: str | None = Field(default=None, description="URL of the most recent stored image.")
    last_update: str | None = Field(default=None, description="ISO 8601 timestamp of last device contact.")
    next_update: str | None = Field(default=None, description="ISO 8601 timestamp of expected next contact.")
    firmware_version: str | None = Field(
        default=None, description="Firmware version reported in the most recent reading, if any."
    )
    wake_reason: str | None = Field(
        default=None, description="Wake reason reported in the most recent reading, if any."
    )


class TimelineItemResponse(ApiModel):
    """One entry in a station's image-capture timeline."""
    timestamp: str = Field(description="ISO 8601 capture timestamp, UTC.")
    url: str = Field(description="URL to fetch the image (relative to the API origin).")


class ImageUploadResponse(ApiModel):
    """Returned after a device upload is successfully stored."""

    filename: str = Field(
        description=(
            "Stored capture filename: the supplied X-Filename when given, otherwise a "
            "server-stamped YYYYMMDD_HHMMZ_default name from the current UTC minute."
        )
    )
    url: str = Field(description="Relative URL where the just-uploaded image can be fetched.")


# Guards on the metric set, to keep a malformed device from writing unbounded
# data. Measurements must be numeric; known metrics are additionally range-checked
# against the registry. Unknown numeric metrics are still accepted.
MAX_METRIC_FIELDS = 64
MAX_METRIC_KEY_LENGTH = 64
# Cap channels (readings) per check-in — same spirit as MAX_METRIC_FIELDS.
MAX_READINGS_PER_REQUEST = 32
# Hard ceiling on total measurements across all readings in one check-in, so a
# single signed request can't write thousands of observations (32 readings x 64
# metrics each would otherwise reach 2048).
MAX_OBSERVATIONS_PER_REQUEST = 512


class ChannelReading(ApiModel):
    """Measurements for one channel within a device check-in.

    The reserved key ``channel`` selects the (metric, channel) series; every other
    key is a numeric measurement (e.g. ``temperature``, ``humidity``, ``voltage``,
    ``battery``): known metrics are validated against the registry's units/ranges;
    unknown numeric metrics are still accepted so a device can report a new field
    without a server-side schema change. Values must be numbers — ``null`` is
    skipped and booleans store as 0/1; any other non-numeric value is rejected. At
    most 64 metric fields, each key at most 64 characters.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="allow"
    )

    channel: str | None = Field(
        default=None,
        description=(
            "Optional channel that groups measurements into a per-(metric, channel) "
            "series, so one station can carry several sensors of the same metric "
            "(e.g. `indoor` vs `outdoor`). Letters, digits, '.', '_' and '-' only, "
            "max 64 chars. Defaults to `default` when omitted; resolved channels "
            "must be unique across a request's readings."
        ),
    )

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > MAX_METRIC_KEY_LENGTH:
            raise ValueError("channel is too long.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", cleaned):
            raise ValueError("channel may only contain letters, digits, '.', '_' and '-'.")
        return cleaned

    @model_validator(mode="after")
    def validate_metrics(self) -> "ChannelReading":
        extras = self.model_extra or {}
        if len(extras) > MAX_METRIC_FIELDS:
            raise ValueError(f"At most {MAX_METRIC_FIELDS} metric fields are allowed.")
        for key, value in extras.items():
            if key in RESERVED_READING_KEYS:
                raise ValueError(
                    f"'{key}' is an envelope label and must be sent at the top "
                    "level, not inside a reading."
                )
            if len(key) > MAX_METRIC_KEY_LENGTH:
                raise ValueError(f"Metric key '{key[:16]}…' is too long.")
            if value is None or isinstance(value, bool):
                continue  # null skipped at ingest; bool stored as 0/1
            if not isinstance(value, (int, float)):
                raise ValueError(f"Metric '{key}' must be a number (or null).")
            spec = METRICS.get(key)
            if spec is not None and not (spec.minimum <= value <= spec.maximum):
                raise ValueError(
                    f"Metric '{key}'={value} is outside the allowed range "
                    f"[{spec.minimum}, {spec.maximum}] {spec.unit}."
                )
        return self

    @property
    def resolved_channel(self) -> str:
        """The channel to store on, with the primary-channel default applied."""
        return self.channel or DEFAULT_CHANNEL

    @property
    def metrics(self) -> dict:
        """Numeric measurements only (reserved keys and nulls excluded)."""
        return {
            key: value
            for key, value in (self.model_extra or {}).items()
            if value is not None and key not in RESERVED_READING_KEYS
        }


class SensorReadingRequest(ApiModel):
    """One device check-in: a shared envelope plus zero or more per-channel readings.

    Envelope fields apply to the whole check-in: ``timestamp`` (server stamps
    receipt time when omitted), ``nextStart``, and the device labels
    ``firmwareVersion`` / ``wakeReason`` (stored on the reading envelope, not as
    measurements). ``readings`` carries the measurements, one entry per channel;
    a single-channel device may omit ``channel`` (defaults to ``default``).
    Resolved channels must be unique within the request. ``readings`` may be
    omitted/empty for an envelope-only check-in (e.g. an online-status heartbeat).
    Unknown top-level keys are rejected — measurements belong inside ``readings``.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    timestamp: str | None = Field(
        default=None,
        description=(
            "Measurement time as an ISO 8601 date-time (e.g. `2026-05-24T14:30:00Z`). "
            "A trailing `Z` or an explicit offset is honoured; a value with no "
            "timezone is assumed to be UTC. Stored normalised to UTC. Omit to have "
            "the server stamp the current UTC time on receipt."
        ),
    )
    next_start: str | None = Field(
        default=None,
        description=(
            "When the device next expects to wake and check in, as an ISO 8601 "
            "date-time (e.g. `2026-05-24T15:00:00Z`; same timezone rules as "
            "`timestamp`). Stored as the reading's next-online hint, which keeps the "
            "station shown as online until this time plus a short grace buffer has "
            "passed."
        ),
    )
    firmware_version: str | None = Field(
        default=None,
        description=(
            "Free-form firmware version label stored on the reading, not a "
            "measurement (e.g. `openmv-n6-2026.05`)."
        ),
    )
    wake_reason: str | None = Field(
        default=None,
        description=(
            "Free-form label for why the device woke, stored on the reading, not a "
            "measurement (e.g. `timer`)."
        ),
    )
    readings: list[ChannelReading] = Field(
        default_factory=list,
        max_length=MAX_READINGS_PER_REQUEST,
        description=(
            "Per-channel measurements for this check-in, one entry per channel. Each "
            "entry's `channel` is optional (defaults to `default`) but resolved "
            f"channels must be unique. At most {MAX_READINGS_PER_REQUEST} readings. "
            "Omit or leave empty for an envelope-only check-in."
        ),
    )

    @field_validator("timestamp", "next_start")
    @classmethod
    def validate_timestamp_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = parse_iso_timestamp(value)
        if parsed is None:
            raise ValueError("Timestamp must be ISO 8601.")
        return iso_utc(parsed)

    @model_validator(mode="after")
    def validate_readings(self) -> "SensorReadingRequest":
        seen: set[str] = set()
        total_metrics = 0
        for reading in self.readings:
            channel = reading.resolved_channel
            if channel in seen:
                raise ValueError(
                    f"Duplicate channel '{channel}' in readings; resolved channels "
                    "must be unique within a check-in."
                )
            seen.add(channel)
            total_metrics += len(reading.metrics)
        if total_metrics > MAX_OBSERVATIONS_PER_REQUEST:
            raise ValueError(
                f"At most {MAX_OBSERVATIONS_PER_REQUEST} measurements are allowed "
                "per check-in."
            )
        return self


class SensorSeriesPoint(ApiModel):
    """One (timestamp, value) sample within a series."""

    timestamp: str = Field(description="ISO 8601 sample timestamp, UTC.")
    value: float = Field(description="Measured value, in the series' canonical unit.")


class SensorSeries(ApiModel):
    """A station's history for one (metric, channel), as an ordered point series."""

    metric: str = Field(description="Canonical metric name (e.g. 'temperature').")
    channel: str = Field(description="Sensor channel within the station.")
    unit: str | None = Field(default=None, description="Canonical unit, or null for an unregistered metric.")
    points: list[SensorSeriesPoint] = Field(description="Samples ordered oldest-to-newest.")
