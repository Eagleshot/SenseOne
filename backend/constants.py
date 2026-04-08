"""Constants for the Eagleshot API."""

import re

# Image handling
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
EMBEDDED_FILENAME_TIMESTAMP_PATTERN = re.compile(r"(\d{8})_(\d{4})Z")

# Database
CAMERA_DB_FILENAME = "camera.db"
CAMERA_CONFIG_FILENAME = "config.yaml"

# Authentication
AUTH_COOKIE_NAME = "eagleshot_session"
AUTH_COOKIE_SECURE = True
AUTH_COOKIE_SAMESITE = "strict"

# OpenAPI documentation
OPENAPI_TAGS = [
    {"name": "System", "description": "Health and service metadata endpoints."},
    {"name": "Auth", "description": "Authentication and session management."},
    {"name": "Stations", "description": "Station metadata, images, history, timeline, weather, and configuration."},
    {"name": "Uploads", "description": "Protected image upload endpoints for stations."},
]

DOC_PATH_ORDER = [
    "/",
    "/health",
    "/auth/login",
    "/auth/me",
    "/auth/logout",
    "/timezones",
    "/stations",
    "/stations/{station_id}",
    "/stations/{station_id}/images/{filename}",
    "/stations/{station_id}/timeline",
    "/stations/{station_id}/history",
    "/stations/{station_id}/weather/current",
    "/stations/{station_id}/weather/forecast",
    "/stations/{station_id}/config",
    "/upload",
    "/upload/{camera_id}",
]

# Status thresholds
DEFAULT_ONLINE_THRESHOLD_MINUTES = 120
