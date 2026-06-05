"""Standalone HMAC request signer for Eagleshot device clients (CPython).

Pure standard library — no backend imports — so it can be dropped onto a
Raspberry Pi (or any CPython device) next to ``requests`` and used as-is.
Produces the v1 signed-request headers the server's ``station_hmac`` verifier
accepts. The per-station shared secret is used only as the HMAC key and never
travels over the wire, so signed requests are safe even over plain HTTP.

Wire format (must stay byte-for-byte identical to backend/station_hmac.py):

    canonical = "\\n".join([
        "v1",
        station_id,
        str(timestamp),          # unix seconds
        nonce_hex,               # >=16 hex chars, fresh per request
        METHOD.upper(),
        path,                    # request path, no query string
        sha256(body).hexdigest(),
    ]).encode("ascii")
    signature = HMAC_SHA256(secret, canonical).hexdigest()

attached as headers::

    X-Station-Id: <station_id>
    X-Timestamp:  <timestamp>
    X-Nonce:      <nonce_hex>
    X-Signature:  v1=<signature>

Example (Raspberry Pi / any host)::

    import eagleshot_signing, requests

    STATION_ID = "rhone-glacier"
    SECRET_B64 = "<paste from rotate-device-secret>"
    body = open("/path/to/capture.jpg", "rb").read()
    path = f"/v1/ingest/stations/{STATION_ID}/images"

    headers = eagleshot_signing.sign_request(
        station_id=STATION_ID, secret_b64=SECRET_B64,
        method="POST", path=path, body=body,
    )
    headers.update({"Content-Type": "image/jpeg",
                    "X-Filename": "20260524_1430Z_front.jpg"})
    requests.post(f"https://api.example.com{path}", data=body, headers=headers)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

SIGNATURE_VERSION = "v1"
NONCE_BYTES = 16


def _b64decode_urlsafe_nopad(value: str) -> bytes:
    """Decode a base64url secret that may be stored without ``=`` padding."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def canonical_signing_string(
    *,
    station_id: str,
    timestamp: int,
    nonce: str,
    method: str,
    path: str,
    body_sha256_hex: str,
) -> bytes:
    """Build the canonical string fed to HMAC. Mirrors the server exactly."""
    return "\n".join((
        SIGNATURE_VERSION,
        station_id,
        str(int(timestamp)),
        nonce,
        method.upper(),
        path,
        body_sha256_hex,
    )).encode("ascii")


def sign_request(
    *,
    station_id: str,
    secret_b64: str,
    method: str,
    path: str,
    body: bytes,
    timestamp: int | None = None,
    nonce_hex: str | None = None,
) -> dict[str, str]:
    """Return the four signed-request headers for a device call.

    ``timestamp`` defaults to the current unix time and ``nonce_hex`` to a
    fresh 16-byte random hex string; pass them explicitly only for tests.
    """
    if timestamp is None:
        timestamp = int(time.time())
    if nonce_hex is None:
        nonce_hex = os.urandom(NONCE_BYTES).hex()

    canonical = canonical_signing_string(
        station_id=station_id,
        timestamp=timestamp,
        nonce=nonce_hex,
        method=method,
        path=path,
        body_sha256_hex=hashlib.sha256(body).hexdigest(),
    )
    secret = _b64decode_urlsafe_nopad(secret_b64)
    signature_hex = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    return {
        "X-Station-Id": station_id,
        "X-Timestamp": str(int(timestamp)),
        "X-Nonce": nonce_hex,
        "X-Signature": f"{SIGNATURE_VERSION}={signature_hex}",
    }
