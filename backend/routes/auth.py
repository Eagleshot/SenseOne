"""Authentication routes."""

from fastapi import APIRouter, Depends, Request, Response, status, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api_docs import error_response
from models import LoginRequest, AuthResponse, MeResponse, SuccessResponse
from auth import (
    auth_cookie_secure,
    bearer_scheme,
    check_login_throttle,
    clear_login_failures,
    create_session,
    ensure_auth_configured,
    get_current_user,
    record_login_failure,
    remove_session,
    resolve_session_token,
    throttle_client_ip,
)
from constants import AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE
from db import user_repo

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in",
    description=(
        "Verify an email and password and start a session. Browsers receive a "
        "session cookie; other clients may use its value as a bearer token."
    ),
    responses={
        401: error_response("Invalid email or password."),
        503: error_response("Authentication is unavailable."),
    },
)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    ensure_auth_configured()

    email = payload.email
    client_ip = throttle_client_ip(request)
    check_login_throttle(client_ip, email)

    user = user_repo.user_authenticate(email, payload.password)
    if user is None:
        record_login_failure(client_ip, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    clear_login_failures(client_ip, user.email)
    # Prune on login, not per request: session validation already filters on
    # expiry, so stale rows are only clutter — and logins are rare enough to
    # carry the cleanup.
    user_repo.sessions_prune_expired()
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
    description="Return the user associated with the current session.",
    responses={
        401: error_response("A valid session is required."),
        503: error_response("Authentication is unavailable."),
    },
)
def me(user=Depends(get_current_user)) -> MeResponse:
    return MeResponse(email=user.email, is_admin=user.is_admin)


@router.post(
    "/logout",
    response_model=SuccessResponse,
    summary="Log out",
    description="End the current session and clear its cookie. This action is idempotent.",
)
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> SuccessResponse:
    token = resolve_session_token(request, credentials)
    if token:
        remove_session(token)
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return SuccessResponse(success=True)
