"""Authentication routes."""

from fastapi import APIRouter, Depends, Request, Response, status, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from models import LoginRequest, AuthResponse, MeResponse
from auth import (
    bearer_scheme,
    check_login_throttle,
    clear_login_failures,
    create_session,
    ensure_auth_configured,
    get_current_user,
    record_login_failure,
    remove_session,
    resolve_session_token,
)
from constants import AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE, auth_cookie_secure
from users import authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in",
    description=(
        "Verify email + password and start a session. On success, sets the "
        "`eagleshot_session` cookie (HttpOnly, SameSite=Strict; Secure whenever "
        "`APP_REQUIRE_HTTPS` is enabled). The session token is delivered only via "
        "that `Set-Cookie` header — it is not echoed in the response body. "
        "Non-browser clients may capture the cookie value and resend it as an "
        "`Authorization: Bearer <token>` header. Programmatic API access will "
        "later get dedicated, revocable API keys rather than reusing this "
        "short-lived browser session.\n\n"
        "Per-IP and per-username throttling kicks in after repeated failures; "
        "successful logins reset both counters."
    ),
)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    ensure_auth_configured()

    email = payload.email
    client_ip = request.client.host if request.client else "unknown"
    check_login_throttle(client_ip, email)

    user = authenticate_user(email, payload.password)
    if user is None:
        record_login_failure(client_ip, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    clear_login_failures(client_ip, user.email)
    token, expires_in = create_session(user.email)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=auth_cookie_secure(),
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )

    return AuthResponse(expires_in=expires_in, email=user.email, is_admin=user.is_admin)


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
    return MeResponse(email=user.email, is_admin=user.is_admin)


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
        remove_session(token)
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}
