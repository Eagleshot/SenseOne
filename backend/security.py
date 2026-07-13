"""Password/secret hashing primitives (PBKDF2-SHA256).

Kept dependency-free (stdlib + utils only) and separate from auth.py so the data
layer (db.sqlite_repo) and users.py can hash/verify secrets without importing the
FastAPI-flavoured auth module — which would otherwise form an import cycle, since
auth.py itself reaches into db.sqlite_repo for session storage.
"""

import hashlib
import hmac
import secrets

from utils import b64url_decode_nopad, b64url_encode_nopad

PBKDF2_ALGO = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
PBKDF2_HASH_BYTES = 32


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
