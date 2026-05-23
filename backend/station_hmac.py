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
    <sha256(body)_hex_lowercase>

Notes:
- Query strings are NOT signed in v1. Don't put security-relevant data in
  the query string on signed routes.
- The shared secret never goes over the wire.
- Replay protection: timestamp must be within +-TIMESTAMP_SKEW_SECONDS,
  and each (station_id, nonce) is single-use within NONCE_RETENTION_SECONDS.
"""

import base64
import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException, Request, status

from config import (
    get_data_dir,
    read_station_device_hmac_secret_b64,
    write_station_meta,
)
from station_access import require_station_exists


SIGNATURE_VERSION = "v1"
TIMESTAMP_SKEW_SECONDS = 300
NONCE_RETENTION_SECONDS = 2 * TIMESTAMP_SKEW_SECONDS
DEVICE_HMAC_SECRET_BYTES = 32
NONCE_DB_FILENAME = "device_nonces.db"
MIN_NONCE_HEX_LENGTH = 16
SIGNATURE_HEX_LENGTH = 64


def _b64encode_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode_nopad(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def generate_device_hmac_secret_b64() -> str:
    """Return a fresh base64url-encoded device HMAC secret (no padding)."""
    return _b64encode_nopad(secrets.token_bytes(DEVICE_HMAC_SECRET_BYTES))


def provision_device_hmac_secret(station_id: str) -> str:
    """Generate, persist, and return a fresh device HMAC secret for a station.

    Returns the secret in base64url form. This is the only chance to read it:
    after this call, the device firmware needs the value but the server does
    not expose it again.
    """
    require_station_exists(station_id)
    secret_b64 = generate_device_hmac_secret_b64()
    write_station_meta(get_data_dir(), station_id, device_hmac_secret_b64=secret_b64)
    return secret_b64


def canonical_signing_string(
    *,
    station_id: str,
    timestamp: int,
    nonce: str,
    method: str,
    path: str,
    body_sha256_hex: str,
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
    )).encode("ascii")


def compute_signature_hex(secret: bytes, message: bytes) -> str:
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _nonce_db_path() -> Path:
    return get_data_dir() / NONCE_DB_FILENAME


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
    db_path = _nonce_db_path()
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
    use the returned bytes (or request.state.verified_body) rather than
    re-streaming the request.
    """
    require_station_exists(station_id)

    header_station = request.headers.get("X-Station-Id", "").strip()
    raw_timestamp = request.headers.get("X-Timestamp", "").strip()
    nonce = request.headers.get("X-Nonce", "").strip().lower()
    raw_signature = request.headers.get("X-Signature", "").strip()

    if not (header_station and raw_timestamp and nonce and raw_signature):
        _reject("Missing signed-request headers.")

    if not hmac.compare_digest(header_station, station_id):
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

    secret_b64 = read_station_device_hmac_secret_b64(get_data_dir(), station_id)
    if not secret_b64:
        _reject("Station has no device HMAC secret provisioned.")
        return b""
    try:
        secret = _b64decode_nopad(secret_b64)
    except (ValueError, base64.binascii.Error):
        _reject("Station device HMAC secret is malformed.")
        return b""

    body = await request.body()
    body_sha256_hex = hashlib.sha256(body).hexdigest()

    canonical = canonical_signing_string(
        station_id=station_id,
        timestamp=timestamp,
        nonce=nonce,
        method=request.method,
        path=request.url.path,
        body_sha256_hex=body_sha256_hex,
    )
    expected_sig_hex = compute_signature_hex(secret, canonical)

    if not hmac.compare_digest(expected_sig_hex, provided_sig_hex):
        _reject("Signature mismatch.")

    if not _register_nonce(station_id, nonce, now):
        _reject("Nonce already used.")

    request.state.verified_body = body
    return body
