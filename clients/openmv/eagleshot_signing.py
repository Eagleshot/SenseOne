"""HMAC request signing for Eagleshot device uploads (MicroPython).

Mirror of clients/python/eagleshot_signing.py and backend/station_hmac.py.
Uses only hashlib + os + binascii, all in the stock OpenMV firmware. HMAC
is implemented inline so the device doesn't depend on the (sometimes
absent) MicroPython `hmac` module.

Devices need a unix timestamp the server will accept. Without an RTC,
fetch GET /v1/server-time once at boot and track offset against
time.ticks_ms().
"""

import binascii
import hashlib
import os


SIGNATURE_VERSION = "v1"
NONCE_BYTES = 16
SHA256_BLOCK_SIZE = 64


def _sha256(data):
    return hashlib.sha256(data).digest()


def _xor_bytes(data, pad):
    result = bytearray(len(data))
    for i in range(len(data)):
        result[i] = data[i] ^ pad
    return bytes(result)


def hmac_sha256(key, msg):
    """Pure-Python HMAC-SHA256."""
    if len(key) > SHA256_BLOCK_SIZE:
        key = _sha256(key)
    if len(key) < SHA256_BLOCK_SIZE:
        key = key + b"\x00" * (SHA256_BLOCK_SIZE - len(key))
    inner = _sha256(_xor_bytes(key, 0x36) + msg)
    return _sha256(_xor_bytes(key, 0x5c) + inner)


def _b64decode_urlsafe_nopad(value):
    """Decode urlsafe-base64-no-padding to raw bytes."""
    s = value.replace("-", "+").replace("_", "/")
    pad = (-len(s)) % 4
    return binascii.a2b_base64(s + ("=" * pad))


def _hexlify(data):
    return binascii.hexlify(data).decode("ascii")


def canonical_signing_string(station_id, timestamp, nonce_hex, method, path, body):
    body_sha256_hex = _hexlify(_sha256(body))
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
    station_id,
    secret_b64,
    method,
    path,
    body,
    timestamp,
    nonce_hex=None,
):
    """Return the four headers to attach to a signed device request."""
    if nonce_hex is None:
        nonce_hex = _hexlify(os.urandom(NONCE_BYTES))
    secret = _b64decode_urlsafe_nopad(secret_b64)
    canonical = canonical_signing_string(
        station_id, timestamp, nonce_hex, method, path, body
    )
    signature_hex = _hexlify(hmac_sha256(secret, canonical))
    return {
        "X-Station-Id": station_id,
        "X-Timestamp": str(int(timestamp)),
        "X-Nonce": nonce_hex,
        "X-Signature": "%s=%s" % (SIGNATURE_VERSION, signature_hex),
    }
