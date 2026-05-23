"""Authentication routes."""

from fastapi import APIRouter, Depends, Request, Response, status, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from models import LoginRequest, AuthResponse, MeResponse
from auth import (
    AUTH_SESSIONS,
    bearer_scheme,
    check_login_throttle,
    clear_login_failures,
    create_session,
    ensure_auth_configured,
    get_current_user,
    record_login_failure,
    resolve_session_token,
)
from constants import AUTH_COOKIE_NAME, AUTH_COOKIE_SECURE, AUTH_COOKIE_SAMESITE
from users import authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in",
    description=(
        "Verify username + password and start a session. On success, sets the "
        "`eagleshot_session` cookie (HttpOnly, Secure, SameSite=Strict) and "
        "returns the same token in the body for non-browser clients to reuse "
        "as a bearer token.\n\n"
        "Per-IP and per-username throttling kicks in after repeated failures; "
        "successful logins reset both counters."
    ),
)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    ensure_auth_configured()

    username = payload.username.strip()
    client_ip = request.client.host if request.client else "unknown"
    check_login_throttle(client_ip, username)

    user = authenticate_user(username, payload.password)
    if user is None:
        record_login_failure(client_ip, username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    clear_login_failures(client_ip, user.username)
    token, expires_in = create_session(user.username)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )

    return AuthResponse(expires_in=expires_in, username=user.username, is_admin=user.is_admin)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Current authenticated user",
    description=(
        "Return the username and admin flag for the session attached to this "
        "request (cookie or bearer token). Returns 401 if no session is present "
        "or the session has expired."
    ),
)
def me(user=Depends(get_current_user)) -> MeResponse:
    return MeResponse(username=user.username, is_admin=user.is_admin)


@router.post(
    "/logout",
    summary="Log out",
    description=(
        "Invalidate the current session (cookie or bearer) and clear the "
        "session cookie. Idempotent — calling without a session still returns 200."
    ),
)
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    token = resolve_session_token(request, credentials)
    if token:
        AUTH_SESSIONS.pop(token, None)
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}
