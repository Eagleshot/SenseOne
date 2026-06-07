"""HMAC request-signing verification for station device requests.

Wire format (version v1) — devices must compute and send the following
headers on every signed request:

    X-Station-Id: <station_id>
    X-Timestamp: <unix_seconds_integer>
    X-Nonce:     <hex, >=16 chars, fresh per request>
    X-Signature: v1=<hex_lowercase_64_chars>

The signature is HMAC-SHA256 over the canonical string:

    v1\\n
    <station_id>\\n
    <timestamp>\\n
    <nonce>\\n
    <METHOD_UPPERCASE>\\n
    <request_path_no_query>\\n
    <sha256(body)_hex_lowercase>\\n
    <x_filename_or_empty>

Notes:
- Query strings are NOT signed in v1. Don't put security-relevant data in
  the query string on signed routes.
- The X-Filename header IS signed (it sets an uploaded image's capture
  timestamp/stream, so it must not be tamperable). Requests that don't send
  X-Filename sign an empty string for that line. Other headers are not signed.
- The shared secret never goes over the wire.
- Replay protection: timestamp must be within +-TIMESTAMP_SKEW_SECONDS,
  and each (station_id, nonce) is single-use within NONCE_RETENTION_SECONDS.
"""

import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException, Request, status

from config import get_data_dir
from db import sqlite_repo
from station_access import require_station_exists
from utils import b64url_decode_nopad, b64url_encode_nopad


SIGNATURE_VERSION = "v1"
TIMESTAMP_SKEW_SECONDS = 300
NONCE_RETENTION_SECONDS = 2 * TIMESTAMP_SKEW_SECONDS
DEVICE_HMAC_SECRET_BYTES = 32
NONCE_DB_FILENAME = "device_nonces.db"
MIN_NONCE_HEX_LENGTH = 16
SIGNATURE_HEX_LENGTH = 64


def generate_device_hmac_secret_b64() -> str:
    """Return a fresh base64url-encoded device HMAC secret (no padding)."""
    return b64url_encode_nopad(secrets.token_bytes(DEVICE_HMAC_SECRET_BYTES))


def provision_device_hmac_secret(station_id: str) -> str:
    """Generate, persist, and return a fresh device HMAC secret for a station.

    Returns the secret in base64url form. This is the only chance to read it:
    after this call, the device firmware needs the value but the server does
    not expose it again.
    """
    require_station_exists(station_id)
    return sqlite_repo.provision_device_secret(station_id)


def canonical_signing_string(
    *,
    station_id: str,
    timestamp: int,
    nonce: str,
    method: str,
    path: str,
    body_sha256_hex: str,
    x_filename: str = "",
) -> bytes:
    """Build the canonical string fed to HMAC. Must match client implementations exactly."""
    return "\n".join((
        SIGNATURE_VERSION,
        station_id,
        str(int(timestamp)),
        nonce,
        method.upper(),
        path,
        body_sha256_hex,
        x_filename,
    )).encode("ascii")


def _ensure_nonce_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS device_nonces (
                station_id TEXT NOT NULL,
                nonce TEXT NOT NULL,
                seen_at REAL NOT NULL,
                PRIMARY KEY (station_id, nonce)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_device_nonces_seen_at ON device_nonces(seen_at)"
        )
        connection.commit()


def _register_nonce(station_id: str, nonce: str, now: float) -> bool:
    """Insert (station_id, nonce). Returns True if fresh, False on replay."""
    db_path = get_data_dir() / NONCE_DB_FILENAME
    _ensure_nonce_db(db_path)
    cutoff = now - NONCE_RETENTION_SECONDS
    with sqlite3.connect(db_path) as connection:
        connection.execute("DELETE FROM device_nonces WHERE seen_at < ?", (cutoff,))
        try:
            connection.execute(
                "INSERT INTO device_nonces (station_id, nonce, seen_at) VALUES (?, ?, ?)",
                (station_id, nonce, now),
            )
        except sqlite3.IntegrityError:
            return False
        connection.commit()
    return True


def _looks_like_lower_hex(value: str) -> bool:
    return bool(value) and all(c in "0123456789abcdef" for c in value)


def _reject(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def verify_station_signature(station_id: str, request: Request) -> bytes:
    """Verify the HMAC signature on a station device request.

    Returns the raw request body on success. Raises HTTPException(401) on any
    failure. The body is read into memory once here; route handlers should
    use the returned bytes rather than re-streaming the request.
    """
    require_station_exists(station_id)

    header_station = request.headers.get("X-Station-Id", "").strip()
    raw_timestamp = request.headers.get("X-Timestamp", "").strip()
    nonce = request.headers.get("X-Nonce", "").strip().lower()
    raw_signature = request.headers.get("X-Signature", "").strip()

    if not (header_station and raw_timestamp and nonce and raw_signature):
        _reject("Missing signed-request headers.")

    # isascii() guards compare_digest, which raises TypeError on non-ASCII str;
    # a non-ASCII station id can never match the (ASCII) path id anyway.
    if not header_station.isascii() or not hmac.compare_digest(header_station, station_id):
        _reject("X-Station-Id does not match request path.")

    scheme_prefix = SIGNATURE_VERSION + "="
    if not raw_signature.startswith(scheme_prefix):
        _reject("Unsupported signature scheme.")
    provided_sig_hex = raw_signature[len(scheme_prefix):].lower()

    try:
        timestamp = int(raw_timestamp)
    except ValueError:
        _reject("Invalid X-Timestamp.")
        return b""

    now = time.time()
    if abs(now - timestamp) > TIMESTAMP_SKEW_SECONDS:
        _reject("Timestamp outside the allowed window.")

    if not _looks_like_lower_hex(nonce) or len(nonce) < MIN_NONCE_HEX_LENGTH:
        _reject("Invalid X-Nonce.")

    if (
        not _looks_like_lower_hex(provided_sig_hex)
        or len(provided_sig_hex) != SIGNATURE_HEX_LENGTH
    ):
        _reject("Invalid X-Signature.")

    secret_b64 = sqlite_repo.read_device_secret_b64(station_id)
    if not secret_b64:
        _reject("Station has no device HMAC secret provisioned.")
        return b""
    try:
        secret = b64url_decode_nopad(secret_b64)
    except ValueError:  # binascii.Error subclasses ValueError
        _reject("Station device HMAC secret is malformed.")
        return b""

    body = await request.body()
    body_sha256_hex = hashlib.sha256(body).hexdigest()

    # X-Filename is signed (see module docstring): it sets an uploaded image's
    # capture timestamp/stream, so an on-path attacker must not be able to alter
    # it. An absent header signs as "". Non-ASCII can never match a valid
    # signature (and would crash the ASCII canonical), so reject it as a 401.
    x_filename = request.headers.get("x-filename", "")
    if not x_filename.isascii():
        _reject("Invalid X-Filename.")

    canonical = canonical_signing_string(
        station_id=station_id,
        timestamp=timestamp,
        nonce=nonce,
        method=request.method,
        path=request.url.path,
        body_sha256_hex=body_sha256_hex,
        x_filename=x_filename,
    )
    expected_sig_hex = hmac.new(secret, canonical, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig_hex, provided_sig_hex):
        _reject("Signature mismatch.")

    if not _register_nonce(station_id, nonce, now):
        _reject("Nonce already used.")

    return body
    
