#!/usr/bin/env python
"""Eagleshot API entrypoint and application construction."""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from constants import API_PREFIX, INGEST_API_PREFIX
from db.migrate import run_migrations
from routes import auth, device_ingestion, stations, system, weather
from settings import get_settings
from users import has_any_user, init_users_db


# Routes that are allowed to be served over plain HTTP even when HTTPS is
# enforced for everything else. Device ingestion uses HMAC signing for its
# auth, which is safe over HTTP. Health/clock endpoints carry no secrets.
HTTP_ALLOWED_PATH_PREFIXES = (f"{INGEST_API_PREFIX}/",)
HTTP_ALLOWED_EXACT_PATHS = {"/", "/health", "/favicon.ico", "/clock"}

# Request-body ceiling for the user-facing API: every non-ingest body is small
# JSON, so anything bigger is abuse (uvicorn has no built-in body limit and
# would buffer it into memory). The signed ingest routes are exempt — they
# carry images and enforce their own caps (see routes/device_ingestion.py).
# h11 enforces Content-Length as a hard upper bound on the actual body, so the
# header can be trusted; chunked requests (no Content-Length) are rejected,
# which no browser/JSON client produces.
MAX_USER_BODY_BYTES = 1 * 1024 * 1024
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


def add_body_size_limit_middleware(app: FastAPI) -> None:
    """Reject oversized (or unsized) request bodies on the non-ingest routes."""

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        if (
            request.method in _BODY_METHODS
            and not request.url.path.startswith(f"{INGEST_API_PREFIX}/")
        ):
            content_length = request.headers.get("content-length")
            if content_length is None:
                return JSONResponse(
                    status_code=status.HTTP_411_LENGTH_REQUIRED,
                    content={"detail": "Content-Length is required."},
                )
            try:
                length = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid Content-Length header."},
                )
            if length > MAX_USER_BODY_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": f"Request body too large. Maximum is {MAX_USER_BODY_BYTES} bytes."},
                )
        return await call_next(request)


def add_security_headers_middleware(app: FastAPI) -> None:
    """Add browser-facing security headers to all responses."""

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), usb=()"
        # HSTS applies only to HTTPS. Don't emit it on the plain-HTTP device
        # ingestion leg (those requests arrive over HTTP by design).
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


def add_https_enforcement_middleware(app: FastAPI) -> None:
    """Reject plain-HTTP requests for routes that carry user credentials."""
    if not get_settings().require_https:
        logging.warning(
            "APP_REQUIRE_HTTPS is not enabled. User-auth routes will accept plain HTTP. "
            "Set APP_REQUIRE_HTTPS=true in production."
        )
        return

    @app.middleware("http")
    async def enforce_https(request: Request, call_next):
        path = request.url.path
        if (
            request.url.scheme == "https"
            or path in HTTP_ALLOWED_EXACT_PATHS
            or any(path.startswith(prefix) for prefix in HTTP_ALLOWED_PATH_PREFIXES)
        ):
            return await call_next(request)
        return JSONResponse(
            status_code=status.HTTP_426_UPGRADE_REQUIRED,
            content={"detail": "HTTPS required for this endpoint."},
        )


def create_app() -> FastAPI:
    """Create and configure the Eagleshot API app."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Fail the boot on a misconfigured environment before touching the database.
    settings = get_settings()
    settings.validate_at_boot()

    # Bring the control-plane schema up to head before anything queries it.
    run_migrations()
    init_users_db()
    if not has_any_user():
        logging.warning(
            "No users exist. Set APP_AUTH_EMAIL and APP_AUTH_PASSWORD to bootstrap an admin."
        )

    app = FastAPI(
        title="Eagleshot API",
        version="0.1.0",
    )
    add_https_enforcement_middleware(app)
    add_body_size_limit_middleware(app)
    add_security_headers_middleware(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Filename"],
    )

    app.include_router(system.router)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(stations.router, prefix=API_PREFIX)
    app.include_router(weather.router, prefix=API_PREFIX)
    app.include_router(device_ingestion.router, prefix=INGEST_API_PREFIX)
    return app


if __name__ == "__main__":
    # Local dev entrypoint: `python main.py`. BACKEND_PORT (from ../.env, default
    # 3000) is the single source of truth for the bind port; uvicorn loads the
    # rest of the config from the same .env, in both the reloader parent and its
    # child processes.
    from pathlib import Path

    import uvicorn
    from dotenv import dotenv_values

    env_file = Path(__file__).resolve().parent.parent / ".env"
    env_values = dotenv_values(env_file) if env_file.exists() else {}
    port = int(env_values.get("BACKEND_PORT") or os.getenv("BACKEND_PORT") or 3000)

    uvicorn.run(
        "main:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
        reload=True,
        env_file=str(env_file) if env_file.exists() else None,
    )
