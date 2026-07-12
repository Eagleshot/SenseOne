"""Authentication and session management."""

import hashlib
import hmac
import time
import secrets
import threading

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from constants import AUTH_COOKIE_NAME
from settings import get_settings
from utils import b64url_decode_nopad, b64url_encode_nopad

PBKDF2_ALGO = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
PBKDF2_HASH_BYTES = 32

# The APP_AUTH_EMAIL/APP_AUTH_PASSWORD bootstrap pair is validated at boot by
# Settings.validate_at_boot() (create_app), not at import time.

AUTH_TOKEN_TTL_SECONDS = 43200

# Sessions live in the control-plane DB (auth_sessions table), so they survive
# restarts/deploys and work across multiple workers. Only the SHA-256 hash of a
# token is stored; the sqlite_repo imports are lazy because db.sqlite_repo
# itself imports hash_secret/verify_secret from this module.
bearer_scheme = HTTPBearer(auto_error=False)

# Login throttling: track recent failures per IP and per username.
LOGIN_FAILURE_WINDOW_SECONDS = 900  # 15 min rolling window
LOGIN_FAILURE_LIMIT = 10
_login_failures: dict[str, list[float]] = {}
_login_failures_lock = threading.Lock()


def auth_cookie_secure() -> bool:
    """Session cookie gets the Secure flag exactly when HTTPS is enforced.

    In local plain-HTTP dev (APP_REQUIRE_HTTPS unset/false) a Secure cookie is
    silently dropped by the browser, so the session would never stick. In
    production APP_REQUIRE_HTTPS is set, so the cookie is Secure as it must be.
    Evaluated per call so it tracks the environment the app booted with.
    """
    return get_settings().require_https


def ensure_auth_configured() -> None:
    """Raise 503 if no users exist (i.e. nothing to authenticate against)."""
    from users import has_any_user

    if has_any_user():
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured.",
    )


def _hash_session_token(token: str) -> str:
    """SHA-256 hex of a session token — what the DB stores instead of the token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(username: str) -> tuple[str, int]:
    """Create a new session for a user."""
    from datetime import datetime, timedelta, timezone

    from db import sqlite_repo

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=AUTH_TOKEN_TTL_SECONDS)
    sqlite_repo.session_create(_hash_session_token(token), username, expires_at)
    return token, AUTH_TOKEN_TTL_SECONDS


def prune_expired_sessions() -> None:
    """Remove expired sessions from storage. Called on login, not per request:
    validation already filters on expiry, so stale rows are only clutter."""
    from db import sqlite_repo

    sqlite_repo.sessions_prune_expired()


def remove_session(token: str) -> None:
    """Invalidate a session token, if present (used on logout)."""
    from db import sqlite_repo

    sqlite_repo.session_delete(_hash_session_token(token))


def resolve_session_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Resolve session token from cookies or headers."""
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


def _validate_session_token(token: str | None) -> str | None:
    """Return the username for a valid unexpired session token, or None."""
    if token is None:
        return None
    from db import sqlite_repo

    return sqlite_repo.session_email(_hash_session_token(token))


def _user_for_token(token: str | None):
    """The User behind a session token, or None — one joined session+user query."""
    if token is None:
        return None
    from users import get_session_user

    return get_session_user(_hash_session_token(token))


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Resolve the User record for the authenticated session."""
    ensure_auth_configured()
    token = resolve_session_token(request, credentials)
    user = _user_for_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required." if token is None else "Invalid or expired session.",
        )
    return user


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Like get_current_user, but returns None instead of raising when unauthenticated."""
    from users import has_any_user

    if not has_any_user():
        return None
    return _user_for_token(resolve_session_token(request, credentials))


def _prune_login_failures(now: float) -> None:
    """Drop login-failure entries older than the rolling window."""
    cutoff = now - LOGIN_FAILURE_WINDOW_SECONDS
    for key in list(_login_failures.keys()):
        kept = [ts for ts in _login_failures[key] if ts > cutoff]
        if kept:
            _login_failures[key] = kept
        else:
            _login_failures.pop(key, None)


def check_login_throttle(client_ip: str, username: str) -> None:
    """Raise 429 if too many recent failures from this IP or username."""
    now = time.time()
    with _login_failures_lock:
        _prune_login_failures(now)
        for key in (f"ip:{client_ip}", f"user:{username}"):
            if len(_login_failures.get(key, ())) >= LOGIN_FAILURE_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Try again later.",
                )


def record_login_failure(client_ip: str, username: str) -> None:
    """Record a failed login attempt for throttling."""
    now = time.time()
    with _login_failures_lock:
        _prune_login_failures(now)
        for key in (f"ip:{client_ip}", f"user:{username}"):
            _login_failures.setdefault(key, []).append(now)


def clear_login_failures(client_ip: str, username: str) -> None:
    """Clear recorded failures after a successful login."""
    with _login_failures_lock:
        _login_failures.pop(f"ip:{client_ip}", None)
        _login_failures.pop(f"user:{username}", None)


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


