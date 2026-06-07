"""Authentication and session management."""

import hashlib
import hmac
import time
import secrets
import os
import threading

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from constants import AUTH_COOKIE_NAME
from utils import b64url_decode_nopad, b64url_encode_nopad

PBKDF2_ALGO = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
PBKDF2_HASH_BYTES = 32


_BOOTSTRAP_EMAIL = (os.getenv("APP_AUTH_EMAIL") or "").strip()
_BOOTSTRAP_PASSWORD = (os.getenv("APP_AUTH_PASSWORD") or "").strip()
if bool(_BOOTSTRAP_EMAIL) != bool(_BOOTSTRAP_PASSWORD):
    raise RuntimeError("APP_AUTH_EMAIL and APP_AUTH_PASSWORD must either both be set or both be unset.")
if _BOOTSTRAP_PASSWORD and len(_BOOTSTRAP_PASSWORD) < 12:
    raise RuntimeError("APP_AUTH_PASSWORD must be at least 12 characters.")

AUTH_TOKEN_TTL_SECONDS = 43200

# In-memory session storage. For multi-replica deploys, swap for Redis or signed JWTs.
# Stored as token -> (username, expires_at). Sync route deps run in FastAPI's
# threadpool, so every access is serialised through _sessions_lock to avoid a
# "dictionary changed size during iteration" crash when pruning races a login.
AUTH_SESSIONS: dict[str, tuple[str, float]] = {}
_sessions_lock = threading.Lock()
bearer_scheme = HTTPBearer(auto_error=False)

# Login throttling: track recent failures per IP and per username.
LOGIN_FAILURE_WINDOW_SECONDS = 900  # 15 min rolling window
LOGIN_FAILURE_LIMIT = 10
_login_failures: dict[str, list[float]] = {}
_login_failures_lock = threading.Lock()


def ensure_auth_configured() -> None:
    """Raise 503 if no users exist (i.e. nothing to authenticate against)."""
    from users import has_any_user

    if has_any_user():
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured.",
    )


def create_session(username: str) -> tuple[str, int]:
    """Create a new session for a user."""
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + AUTH_TOKEN_TTL_SECONDS
    with _sessions_lock:
        AUTH_SESSIONS[token] = (username, expires_at)
    return token, AUTH_TOKEN_TTL_SECONDS


def prune_expired_sessions() -> None:
    """Remove expired sessions from storage."""
    now = time.time()
    with _sessions_lock:
        expired_tokens = [token for token, (_, expires_at) in AUTH_SESSIONS.items() if expires_at <= now]
        for token in expired_tokens:
            AUTH_SESSIONS.pop(token, None)


def remove_session(token: str) -> None:
    """Invalidate a session token, if present (used on logout)."""
    with _sessions_lock:
        AUTH_SESSIONS.pop(token, None)


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
    with _sessions_lock:
        session = AUTH_SESSIONS.get(token)
        if session is None:
            return None
        username, expires_at = session
        if expires_at <= time.time():
            AUTH_SESSIONS.pop(token, None)
            return None
        return username


def get_current_username(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Get the authenticated username from session."""
    ensure_auth_configured()
    prune_expired_sessions()
    token = resolve_session_token(request, credentials)
    username = _validate_session_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required." if token is None else "Invalid or expired session.",
        )
    return username


def get_current_user(username: str = Depends(get_current_username)):
    """Resolve the User record for the authenticated session."""
    from users import get_user

    user = get_user(username)
    if user is None: # The user was deleted while their session was still valid.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")
    return user


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Like get_current_user, but returns None instead of raising when unauthenticated."""
    from users import get_user, has_any_user

    if not has_any_user():
        return None
    prune_expired_sessions()
    token = resolve_session_token(request, credentials)
    username = _validate_session_token(token)
    if username is None:
        return None
    return get_user(username)


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


