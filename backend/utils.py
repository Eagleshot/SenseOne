"""Utility functions for the Eagleshot API."""

import re
from datetime import datetime, timezone
from pathlib import Path

from constants import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_CONTENT_TYPES

_EXTENSION_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_IMAGE_CAPTURE_NAME = re.compile(
    r"^(\d{8})_(\d{4})Z_[A-Za-z0-9._-]+\.(?:jpe?g|png|webp)$",
    re.IGNORECASE,
)


def sanitize_filename(raw_name: str) -> str:
    """Sanitize a filename to prevent path traversal attacks."""
    return re.sub(r"[^a-zA-Z0-9.\-_]", "_", raw_name.strip()) or "default.jpg"


def sanitize_station_id(raw_name: str | None = None, default: str = "default") -> str:
    """Sanitize a station ID."""
    raw = (raw_name or default).strip()
    return re.sub(r"[^a-zA-Z0-9._-]", "-", raw).strip("._-") or default


def unique_station_id(base_dir: Path, requested_id: str | None, default: str = "default") -> str | None:
    """Return a sanitized station id under base_dir that does not exist yet.

    Appends ``-2``, ``-3``, … when the preferred id is taken. Returns None if
    no free id is found within a reasonable range; callers decide how to fail.
    """
    station_id = sanitize_station_id(requested_id, default=default)
    if not (base_dir / station_id).exists():
        return station_id
    for index in range(2, 1000):
        candidate = sanitize_station_id(f"{station_id}-{index}", default=default)
        if not (base_dir / candidate).exists():
            return candidate
    return None


def normalize_content_type(raw_content_type: str | None) -> str | None:
    """Normalize a content-type header value."""
    if not raw_content_type:
        return None
    return raw_content_type.split(";", 1)[0].strip().lower()


def media_type_from_path(path: Path) -> str | None:
    """Determine the media type of an image file."""
    media_type = _EXTENSION_TO_MEDIA_TYPE.get(path.suffix.lower())
    if media_type:
        return media_type
    try:
        header = path.read_bytes()[:16]
    except OSError:
        return None
    if header.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1A\n"):
        return "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def parse_iso_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp string."""
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    """Convert a datetime to ISO 8601 UTC string."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def image_timestamp_from_filename(filename: str) -> datetime | None:
    """Parse a UTC capture timestamp from YYYYMMDD_HHMMZ_<camera> image names."""
    match = _IMAGE_CAPTURE_NAME.match(filename)
    if not match:
        return None

    raw_date, raw_time = match.group(1), match.group(2)
    try:
        return datetime.strptime(raw_date + raw_time, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_supported_image_upload(filename: str, content_type: str | None) -> bool:
    """Check if an image file is supported for upload."""
    extension = Path(filename).suffix.lower()
    extension_ok = extension in ALLOWED_IMAGE_EXTENSIONS

    normalized_ct = normalize_content_type(content_type)
    if normalized_ct and not normalized_ct.startswith("image/"):
        return False
    if normalized_ct and normalized_ct not in ALLOWED_IMAGE_CONTENT_TYPES:
        return False

    return extension_ok or not extension


def humanize_station_id(station_id: str) -> str:
    """Convert a station ID to a human-readable form."""
    return re.sub(r"[-_.]+", " ", station_id).strip().title() or station_id
