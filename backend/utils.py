"""Utility functions for the Eagleshot API."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from constants import EMBEDDED_FILENAME_TIMESTAMP_PATTERN, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_CONTENT_TYPES

_EXTENSION_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _sanitize_string(value: str, allowed_pattern: str, replacement: str = "_", strip_chars: str = "", fallback: str = "") -> str:
    """Generic string sanitization using regex pattern."""
    cleaned = re.sub(allowed_pattern, replacement, value.strip())
    if strip_chars:
        cleaned = cleaned.strip(strip_chars)
    return cleaned or fallback


def sanitize_filename(raw_name: str) -> str:
    """Sanitize a filename to prevent path traversal attacks."""
    return _sanitize_string(raw_name, r"[^a-zA-Z0-9.\-_]", "_", fallback="default.jpg")


def sanitize_camera_id(raw_name: str | None = None, default: str = "default") -> str:
    """Sanitize a camera ID."""
    raw = (raw_name or default).strip()
    return _sanitize_string(raw, r"[^a-zA-Z0-9._-]", "-", "._-", default)

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


def parse_embedded_timestamp(filename: str) -> datetime | None:
    """Parse timestamp embedded in filename (YYYYMMDD_HHmmZ format)."""
    match = EMBEDDED_FILENAME_TIMESTAMP_PATTERN.search(filename)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
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


def to_yaml_value(value: str | None) -> str:
    """Convert a value to YAML-safe string representation."""
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


def humanize_camera_id(camera_id: str) -> str:
    """Convert a camera ID to a human-readable form."""
    return re.sub(r"[-_.]+", " ", camera_id).strip().title() or camera_id
