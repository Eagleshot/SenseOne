"""Authentication and session management."""

import time
import secrets
import os
import threading

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from constants import AUTH_COOKIE_NAME


def parse_positive_int_env(name: str, default: int) -> int:
    """Parse a positive integer environment variable."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than 0.")
    return parsed


AUTH_USERNAME = (os.getenv("APP_AUTH_USERNAME") or "").strip()
AUTH_PASSWORD = (os.getenv("APP_AUTH_PASSWORD") or "").strip()
if bool(AUTH_USERNAME) != bool(AUTH_PASSWORD):
    raise RuntimeError("APP_AUTH_USERNAME and APP_AUTH_PASSWORD must either both be set or both be unset.")

AUTH_ENABLED = bool(AUTH_USERNAME and AUTH_PASSWORD)
if AUTH_ENABLED and len(AUTH_PASSWORD) < 12:
    raise RuntimeError("APP_AUTH_PASSWORD must be at least 12 characters.")

AUTH_TOKEN_TTL_SECONDS = 43200

# In-memory session storage. For multi-replica deploys, swap for Redis or signed JWTs.
AUTH_SESSIONS: dict[str, tuple[str, float]] = {}
bearer_scheme = HTTPBearer(auto_error=False)

# Login throttling: track recent failures per IP and per username.
LOGIN_FAILURE_WINDOW_SECONDS = 900  # 15 min rolling window
LOGIN_FAILURE_LIMIT = 10
_login_failures: dict[str, list[float]] = {}
_login_failures_lock = threading.Lock()


def ensure_auth_configured() -> None:
    """Raise exception if authentication is not configured."""
    if AUTH_ENABLED:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured.",
    )


def create_session(username: str) -> tuple[str, int]:
    """Create a new session for a user."""
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + AUTH_TOKEN_TTL_SECONDS
    AUTH_SESSIONS[token] = (username, expires_at)
    return token, AUTH_TOKEN_TTL_SECONDS


def prune_expired_sessions() -> None:
    """Remove expired sessions from storage."""
    now = time.time()
    expired_tokens = [token for token, (_, expires_at) in AUTH_SESSIONS.items() if expires_at <= now]
    for token in expired_tokens:
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


def get_current_username(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Get the authenticated username from session."""
    ensure_auth_configured()
    prune_expired_sessions()

    token = resolve_session_token(request, credentials)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    session = AUTH_SESSIONS.get(token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

    username, expires_at = session
    if expires_at <= time.time():
        AUTH_SESSIONS.pop(token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

    return username


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password using constant-time comparison.

    Both comparisons run regardless of length or username match so timing
    cannot reveal which field was wrong.
    """
    user_ok = secrets.compare_digest(username.encode("utf-8"), AUTH_USERNAME.encode("utf-8"))
    pwd_ok = secrets.compare_digest(password.encode("utf-8"), AUTH_PASSWORD.encode("utf-8"))
    return user_ok and pwd_ok


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
