#!/usr/bin/env python
"""Eagleshot API entrypoint and application construction."""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from constants import API_V1_PREFIX, DEVICE_API_PREFIX
from routes import auth, device_ingestion, stations, stations_images_weather, system
from users import has_any_user, init_users_db


# Routes that are allowed to be served over plain HTTP even when HTTPS is
# enforced for everything else. Device ingestion uses HMAC signing for its
# auth, which is safe over HTTP. Health/server-time endpoints carry no secrets.
HTTP_ALLOWED_PATH_PREFIXES = (f"{DEVICE_API_PREFIX}/",)
HTTP_ALLOWED_EXACT_PATHS = {"/", "/health", "/favicon.ico", f"{API_V1_PREFIX}/server-time"}


def parse_cors_origins() -> list[str]:
    """Parse CORS origins from environment."""
    raw_value = (os.getenv("APP_CORS_ORIGINS") or "").strip()
    if not raw_value:
        raise RuntimeError("APP_CORS_ORIGINS must be set.")

    origins = [origin.strip().rstrip("/") for origin in raw_value.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("APP_CORS_ORIGINS is set but empty.")
    if "*" in origins:
        raise RuntimeError("Wildcard CORS origins are not allowed.")
    return origins


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
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


def _is_https_optional_path(path: str) -> bool:
    if path in HTTP_ALLOWED_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in HTTP_ALLOWED_PATH_PREFIXES)


def add_https_enforcement_middleware(app: FastAPI) -> None:
    """Reject plain-HTTP requests for routes that carry user credentials."""
    enabled = (os.getenv("APP_REQUIRE_HTTPS") or "").strip().lower() in ("1", "true", "yes")
    if not enabled:
        logging.warning(
            "APP_REQUIRE_HTTPS is not enabled. User-auth routes will accept plain HTTP. "
            "Set APP_REQUIRE_HTTPS=true in production."
        )
        return

    @app.middleware("http")
    async def enforce_https(request: Request, call_next):
        if request.url.scheme == "https" or _is_https_optional_path(request.url.path):
            return await call_next(request)
        return JSONResponse(
            status_code=status.HTTP_426_UPGRADE_REQUIRED,
            content={"detail": "HTTPS required for this endpoint."},
        )


def create_app() -> FastAPI:
    """Create and configure the Eagleshot API app."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_users_db()
    if not has_any_user():
        logging.warning(
            "No user accounts exist. Set APP_AUTH_USERNAME and APP_AUTH_PASSWORD to bootstrap an admin."
        )

    app = FastAPI(
        title="Eagleshot API",
        version="0.1.0",
    )
    add_https_enforcement_middleware(app)
    add_security_headers_middleware(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=parse_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type", "X-Filename"],
    )

    app.include_router(system.router)
    app.include_router(auth.router, prefix=API_V1_PREFIX)
    app.include_router(stations.router, prefix=API_V1_PREFIX)
    app.include_router(stations_images_weather.router, prefix=API_V1_PREFIX)
    app.include_router(device_ingestion.router, prefix=DEVICE_API_PREFIX)
    return app
