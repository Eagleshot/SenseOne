"""Authentication routes."""

from fastapi import APIRouter, Depends, Request, Response, status, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from models import LoginRequest, AuthResponse, MeResponse
from auth import (
    get_current_username,
    ensure_auth_configured,
    create_session,
    verify_credentials,
    resolve_session_token,
    AUTH_SESSIONS,
    bearer_scheme,
)
from constants import AUTH_COOKIE_NAME, AUTH_COOKIE_SECURE, AUTH_COOKIE_SAMESITE

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Create Session",
    description="Authenticate with username and password and create a session cookie.",
)
def login(payload: LoginRequest, response: Response) -> AuthResponse:
    """Authenticate user and create session."""
    ensure_auth_configured()

    username = payload.username.strip()
    is_valid = verify_credentials(username, payload.password)
    
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    token, expires_in = create_session(username)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )

    return AuthResponse(expires_in=expires_in, username=username)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get Current User",
    description="Return the authenticated user associated with the current session or bearer token.",
)
def me(username: str = Depends(get_current_username)) -> MeResponse:
    """Return current authenticated user."""
    return MeResponse(username=username)


@router.post(
    "/logout",
    summary="Delete Session",
    description="Invalidate the current session and clear the authentication cookie.",
)
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Invalidate session and clear cookie."""
    token = resolve_session_token(request, credentials)
    if token:
        AUTH_SESSIONS.pop(token, None)
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}
