#!/usr/bin/env python
"""
Eagleshot API - Camera station monitoring and management.

This application serves as the backend for the Eagleshot project,
providing endpoints for station metadata, images, history, weather,
configuration, and uploads.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

# Import configuration
from constants import OPENAPI_TAGS, DOC_PATH_ORDER
from auth import AUTH_ENABLED

# Import route modules
from routes import system, auth, stations, uploads, stations_images_weather

# Environment configuration
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CAMERA_ID = (os.getenv("APP_DEFAULT_CAMERA_ID") or "default").strip() or "default"

# Parse CORS origins
def parse_cors_origins() -> list[str]:
    """Parse CORS origins from environment."""
    raw_value = (os.getenv("APP_CORS_ORIGINS") or "").strip()
    if raw_value:
        origins = [origin.strip().rstrip("/") for origin in raw_value.split(",") if origin.strip()]
        if not origins:
            raise RuntimeError("APP_CORS_ORIGINS is set but empty.")
        if "*" in origins:
            raise RuntimeError("Wildcard CORS origins are not allowed.")
        return origins
    raise RuntimeError("APP_CORS_ORIGINS must be set.")


# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
if not AUTH_ENABLED:
    logging.warning("Authentication is disabled because APP_AUTH_USERNAME/APP_AUTH_PASSWORD are not set.")

# Create FastAPI application
app = FastAPI(
    title="Eagleshot API",
    version="0.1.0",
    description="API for station metadata, media, history, weather, configuration, and uploads.",
    openapi_tags=OPENAPI_TAGS,
)


# Custom OpenAPI schema ordering
def custom_openapi() -> dict:
    """Generate OpenAPI schema with custom path ordering."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    paths = schema.get("paths", {})
    ordered_paths = {
        path: paths[path]
        for path in sorted(
            paths,
            key=lambda path: (
                DOC_PATH_ORDER.index(path) if path in DOC_PATH_ORDER else len(DOC_PATH_ORDER),
                path,
            ),
        )
    }
    schema["paths"] = ordered_paths
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
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


# Add CORS middleware
APP_CORS_ORIGINS = parse_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Filename", "X-Camera-Id"],
)

# Include routers
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(stations.router)
app.include_router(uploads.router)
app.include_router(stations_images_weather.router)


# Application entry point
if __name__ == "__main__":
    import uvicorn
    from auth import parse_positive_int_env

    port = parse_positive_int_env("PORT", 3000)
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
    )
