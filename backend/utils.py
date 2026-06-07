"""Utility functions for the Eagleshot API."""

import base64
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from constants import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_CONTENT_TYPES

_EXTENSION_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_MEDIA_TYPE_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Capture filename: YYYYMMDD_HHMMZ_<name>[_<stream>].<ext>
#   group 1 date, 2 time, 3 name (optional), 4 stream (optional), 5 ext.
# The frozen station-name token sits right after the timestamp; an optional
# camera/stream token may follow it. Neither token may contain "_" (the
# delimiter), so name and stream stay unambiguously separable.
_IMAGE_CAPTURE_NAME = re.compile(
    r"^(\d{8})_(\d{4})Z(?:_([A-Za-z0-9.-]+)(?:_([A-Za-z0-9.-]+))?)?\.(jpe?g|png|webp)$",
    re.IGNORECASE,
)

# German umlauts expand to digraphs (ü→ue …) before the generic NFKD pass, so a
# Swiss "Zürich" becomes "Zuerich" rather than "Zurich".
_GERMAN_UMLAUTS = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
}
_UMLAUT_TABLE = str.maketrans(_GERMAN_UMLAUTS)
_NAME_TOKEN_MAX_LEN = 40


def sanitize_filename(raw_name: str) -> str:
    """Sanitize a filename to prevent path traversal attacks."""
    return re.sub(r"[^a-zA-Z0-9.\-_]", "_", raw_name.strip()) or "default.jpg"


def sanitize_station_id(raw_name: str | None = None, default: str = "default") -> str:
    """Sanitize a station ID."""
    raw = (raw_name or default).strip()
    return re.sub(r"[^a-zA-Z0-9._-]", "-", raw).strip("._-") or default


def b64url_encode_nopad(data: bytes) -> str:
    """Base64url-encode without padding (device-secret / HMAC / password-hash wire format)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode_nopad(value: str) -> bytes:
    """Decode a base64url string, re-adding any stripped '=' padding."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def ascii_station_name(title: str) -> str:
    """Transliterate a station title to a lowercase, filename-safe ASCII token.

    German umlauts expand (ü→ue, ö→oe, ä→ae, ß→ss); any remaining non-ASCII is
    dropped via NFKD. The result is lowercased, separators collapse to ``-`` (never
    ``_``, which the capture filename uses to delimit the optional stream), and the
    token is capped to keep paths short. The same token also backs the station's
    url_slug, so a station's slug and its image filenames agree (e.g. 'Zürich' →
    'zuerich'). Returns ``""`` when nothing survives (e.g. a non-Latin script) so
    callers can fall back to a stable id — see :func:`station_name_token`.
    """
    expanded = (title or "").translate(_UMLAUT_TABLE)
    ascii_only = unicodedata.normalize("NFKD", expanded).encode("ascii", "ignore").decode("ascii")
    token = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return token[:_NAME_TOKEN_MAX_LEN].strip("-")


def station_name_token(title: str, *, url_slug: str = "", public_id: str = "") -> str:
    """Frozen, lowercase, filename-safe station-name token with fallbacks for an empty transliteration.

    Falls back from the transliterated title to the url_slug, then the opaque
    public_id, then ``"station"`` — never an empty token. Any ``_`` in a fallback
    is replaced with ``-`` and the result is lowercased so the token can't break
    name/stream parsing and matches the url_slug.
    """
    token = ascii_station_name(title) or url_slug or public_id or "station"
    return token.replace("_", "-").lower()


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
    """Convert a datetime to an ISO 8601 UTC string (naive values are assumed UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def image_timestamp_from_filename(filename: str) -> datetime | None:
    """Parse a UTC capture timestamp from YYYYMMDD_HHMMZ[_<name>[_<stream>]] image names."""
    match = _IMAGE_CAPTURE_NAME.match(filename)
    if not match:
        return None

    raw_date, raw_time = match.group(1), match.group(2)
    try:
        return datetime.strptime(raw_date + raw_time, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def stream_from_filename(filename: str) -> str | None:
    """Parse the optional camera/stream token from a YYYYMMDD_HHMMZ_<name>[_<stream>] image name.

    The token right after the timestamp is the (frozen) station name; the stream
    is the *optional* token after it. Returns the ``<stream>`` token (e.g.
    ``thermal``) or None when there is no stream or the name doesn't match the
    capture format (the same names rejected on upload).
    """
    match = _IMAGE_CAPTURE_NAME.match(filename)
    return match.group(4) if match else None


def default_capture_filename(
    content_type: str | None, *, name: str = "default", now: datetime | None = None
) -> str:
    """Build a capture-format filename for an upload that omitted ``X-Filename``.

    Stamps the current UTC minute as the capture time and uses ``name`` as the
    name token (the caller passes the station's frozen name token), so the
    generated name still matches ``YYYYMMDD_HHMMZ_<name>.<ext>`` and flows through
    the same parsing as a device-supplied name. The extension follows the body's
    content type, defaulting to ``.jpg``.
    """
    moment = now or datetime.now(timezone.utc)
    extension = _MEDIA_TYPE_TO_EXTENSION.get(normalize_content_type(content_type) or "", ".jpg")
    return f"{moment:%Y%m%d_%H%MZ}_{name}{extension}"


def inject_name_if_missing(filename: str, name: str) -> str:
    """Expand a bare ``YYYYMMDD_HHMMZ.<ext>`` upload name with the station name token.

    A device may upload just the timestamp; the server fills in the station's
    frozen ASCII name so the stored file is self-identifying. A name that already
    carries a token (``..._<name>`` or ``..._<name>_<stream>``) is returned
    unchanged, as is anything that isn't capture-format.
    """
    match = _IMAGE_CAPTURE_NAME.match(filename)
    if match and match.group(3) is None:
        return f"{match.group(1)}_{match.group(2)}Z_{name}.{match.group(5)}"
    return filename


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
