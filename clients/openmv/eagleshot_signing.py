# HMAC-SHA256 request signing for Eagleshot device firmware (MicroPython).
#
# Pure-Python HMAC so it runs on boards where MicroPython ships no `hmac`
# module. Produces the v1 signed-request headers the server expects; the
# per-station shared secret is only ever used as the HMAC key and never leaves
# the device, so signed requests are safe even over plain HTTP.
#
# Keep this file next to main.py on the board so `import eagleshot_signing`
# resolves. The wire format must stay byte-for-byte identical to the server's
# backend/station_hmac.py and the CPython client in clients/python/.

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
    """Pure-Python HMAC-SHA256 (MicroPython doesn't ship `hmac` everywhere)."""
    if len(key) > SHA256_BLOCK_SIZE:
        key = _sha256(key)
    if len(key) < SHA256_BLOCK_SIZE:
        key = key + b"\x00" * (SHA256_BLOCK_SIZE - len(key))
    inner = _sha256(_xor_bytes(key, 0x36) + msg)
    return _sha256(_xor_bytes(key, 0x5c) + inner)


def _b64decode_urlsafe_nopad(value):
    s = value.replace("-", "+").replace("_", "/")
    pad = (-len(s)) % 4
    return binascii.a2b_base64(s + ("=" * pad))


def _hexlify(data):
    return binascii.hexlify(data).decode("ascii")


def sign_request(station_id, secret_b64, method, path, body, timestamp, nonce_hex=None):
    """Return the four headers to attach to a signed device request."""
    if nonce_hex is None:
        nonce_hex = _hexlify(os.urandom(NONCE_BYTES))
    canonical = "\n".join((
        SIGNATURE_VERSION,
        station_id,
        str(int(timestamp)),
        nonce_hex,
        method.upper(),
        path,
        _hexlify(_sha256(body)),
    )).encode("ascii")
    secret = _b64decode_urlsafe_nopad(secret_b64)
    signature_hex = _hexlify(hmac_sha256(secret, canonical))
    return {
        "X-Station-Id": station_id,
        "X-Timestamp": str(int(timestamp)),
        "X-Nonce": nonce_hex,
        "X-Signature": "%s=%s" % (SIGNATURE_VERSION, signature_hex),
    }
