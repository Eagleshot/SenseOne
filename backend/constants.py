"""Constants for the Eagleshot API."""

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
CAMERA_DB_FILENAME = "camera.db"
CAMERA_CONFIG_FILENAME = "config.yaml"

AUTH_COOKIE_NAME = "eagleshot_session"
AUTH_COOKIE_SECURE = True
AUTH_COOKIE_SAMESITE = "strict"

API_V1_PREFIX = "/v1"
DEVICE_API_PREFIX = f"{API_V1_PREFIX}/device"

DEFAULT_ONLINE_THRESHOLD_MINUTES = 120
NEXT_ONLINE_STATUS_BUFFER_MINUTES = 5
