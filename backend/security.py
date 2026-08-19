"""Secret primitives: PBKDF2-SHA256 hashing and device-secret generation.

Kept dependency-free (stdlib + utils only) and separate from auth.py so the data
layer can hash/verify/generate secrets without importing the FastAPI-flavoured
auth module — which would otherwise form an import cycle, since auth.py itself
reaches into the data layer for session storage.
"""

import hashlib
import hmac
import secrets
from functools import cache

from utils import b64url_decode_nopad, b64url_encode_nopad

PBKDF2_ALGO = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
PBKDF2_HASH_BYTES = 32

DEVICE_HMAC_SECRET_BYTES = 32


def generate_device_hmac_secret_b64() -> str:
    """Return a fresh base64url-encoded device HMAC secret (no padding)."""
    return b64url_encode_nopad(secrets.token_bytes(DEVICE_HMAC_SECRET_BYTES))


def hash_secret(secret: str) -> str:
    """Hash a password or API key using PBKDF2-SHA256."""
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=PBKDF2_HASH_BYTES,
    )
    return "${algo}${iters}${salt}${hash}".format(
        algo=PBKDF2_ALGO,
        iters=PBKDF2_ITERATIONS,
        salt=b64url_encode_nopad(salt),
        hash=b64url_encode_nopad(digest),
    )


def verify_secret(secret: str, stored: str | None) -> bool:
    """Verify a secret against its stored hash. Constant-time comparison."""
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 5 or parts[0] != "" or parts[1] != PBKDF2_ALGO:
        return False
    try:
        iterations = int(parts[2])
        salt = b64url_decode_nopad(parts[3])
        expected = b64url_decode_nopad(parts[4])
    except ValueError:  # binascii.Error subclasses ValueError
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected),
    )
    return hmac.compare_digest(digest, expected)


@cache
def dummy_password_hash() -> str:
    """A hash with the same PBKDF2 cost as a real one, so the unknown-email login
    path spends the same time as a known-user failure (timing-based
    account-enumeration defense).

    Computed on first use (and cached), not at import: importing this module —
    which every route module does transitively — otherwise pays ~600k PBKDF2
    iterations at boot even for processes that never hit the login path.
    """
    return hash_secret("eagleshot-dummy-password-for-timing")
