"""Reference HMAC signing for Eagleshot station device requests.

Mirror of the server's wire format in backend/station_hmac.py. Devices that
use this module never transmit the shared secret — they prove possession by
signing a canonical request string. Safe to use over plain HTTP.

Usage:

    secret_b64 = "..."   # provisioned once, stored in device flash
    headers = sign_request(
        station_id="silvretta-glacier",
        secret_b64=secret_b64,
        method="POST",
        path="/device/stations/silvretta-glacier/images",
        body=jpeg_bytes,
    )
    requests.post(url, data=jpeg_bytes, headers={**headers, "Content-Type": "image/jpeg"})
"""

import base64
import hashlib
import hmac
import os
import time


SIGNATURE_VERSION = "v1"
NONCE_BYTES = 16


def _b64decode_nopad(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def canonical_signing_string(
    *,
    station_id: str,
    timestamp: int,
    nonce_hex: str,
    method: str,
    path: str,
    body: bytes,
) -> bytes:
    body_sha256_hex = hashlib.sha256(body).hexdigest()
    return "\n".join((
        SIGNATURE_VERSION,
        station_id,
        str(int(timestamp)),
        nonce_hex,
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
    """Return the four headers to attach to a signed device request.

    timestamp and nonce_hex are exposed for testing; in production let them
    default so each request gets a fresh nonce and current timestamp.
    """
    if timestamp is None:
        timestamp = int(time.time())
    if nonce_hex is None:
        nonce_hex = os.urandom(NONCE_BYTES).hex()

    secret = _b64decode_nopad(secret_b64)
    message = canonical_signing_string(
        station_id=station_id,
        timestamp=timestamp,
        nonce_hex=nonce_hex,
        method=method,
        path=path,
        body=body,
    )
    signature_hex = hmac.new(secret, message, hashlib.sha256).hexdigest()

    return {
        "X-Station-Id": station_id,
        "X-Timestamp": str(timestamp),
        "X-Nonce": nonce_hex,
        "X-Signature": f"{SIGNATURE_VERSION}={signature_hex}",
    }


if __name__ == "__main__":
    import json
    example = sign_request(
        station_id="silvretta-glacier",
        secret_b64="this-would-come-from-provisioning",
        method="POST",
        path="/device/stations/silvretta-glacier/images",
        body=b"\xff\xd8\xff\xe0fake-jpeg",
    )
    print(json.dumps(example, indent=2))
