"""Constants for the Eagleshot API."""

import os


def env_flag(name: str) -> bool:
    """True when an environment variable is set to a truthy value."""
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

AUTH_COOKIE_NAME = "eagleshot_session"
AUTH_COOKIE_SAMESITE = "strict"


def auth_cookie_secure() -> bool:
    """Session cookie gets the Secure flag exactly when HTTPS is enforced.

    In local plain-HTTP dev (APP_REQUIRE_HTTPS unset/false) a Secure cookie is
    silently dropped by the browser, so the session would never stick. In
    production APP_REQUIRE_HTTPS is set, so the cookie is Secure as it must be.
    Evaluated per call so it tracks the environment the app booted with.
    """
    return env_flag("APP_REQUIRE_HTTPS")

API_PREFIX = "/v1"
INGEST_API_PREFIX = f"{API_PREFIX}/ingest"

NEXT_ONLINE_STATUS_BUFFER_MINUTES = 5
