"""Constants for the Eagleshot API."""

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

AUTH_COOKIE_NAME = "eagleshot_session"
AUTH_COOKIE_SAMESITE = "strict"

API_PREFIX = "/v1"
INGEST_API_PREFIX = f"{API_PREFIX}/ingest"

NEXT_ONLINE_STATUS_BUFFER_MINUTES = 5
