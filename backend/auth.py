"""Authentication and session management."""

import time
import secrets
import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


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

# In-memory session storage (should be replaced with Redis or database in production)
AUTH_SESSIONS: dict[str, tuple[str, float]] = {}
bearer_scheme = HTTPBearer(auto_error=False)


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
    from constants import AUTH_COOKIE_NAME
    
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
    """Verify username and password against configured credentials."""
    return secrets.compare_digest(username, AUTH_USERNAME) and secrets.compare_digest(password, AUTH_PASSWORD)
