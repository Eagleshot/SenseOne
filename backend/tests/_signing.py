"""Local request signer for tests.

Replaces the former external Python client SDK (``clients/python``). Produces
the v1 HMAC headers the server's ``station_hmac`` verifier accepts, using the
server's own canonical-string builder so the two can never drift.
"""

import base64
import hashlib
import hmac
import os
import time

from station_hmac import SIGNATURE_VERSION, canonical_signing_string


def _b64decode_nopad(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


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
    """Return the four signed-request headers for a device call."""
    if timestamp is None:
        timestamp = int(time.time())
    if nonce_hex is None:
        nonce_hex = os.urandom(16).hex()

    canonical = canonical_signing_string(
        station_id=station_id,
        timestamp=timestamp,
        nonce=nonce_hex,
        method=method,
        path=path,
        body_sha256_hex=hashlib.sha256(body).hexdigest(),
    )
    secret = _b64decode_nopad(secret_b64)
    signature_hex = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    return {
        "X-Station-Id": station_id,
        "X-Timestamp": str(int(timestamp)),
        "X-Nonce": nonce_hex,
        "X-Signature": f"{SIGNATURE_VERSION}={signature_hex}",
    }
