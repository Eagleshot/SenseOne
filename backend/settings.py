"""Central runtime configuration, read from the process environment.

Every environment variable the backend consumes is read here (the only
exceptions: ``BACKEND_PORT`` in main.py's dev entrypoint and
``TEST_DATABASE_URL`` in the test harness). ``get_settings()`` builds a fresh
immutable snapshot per call, so values track the live environment exactly like
the scattered ``os.getenv`` reads it replaces — tests can monkeypatch env vars
per test, and ``auth_cookie_secure`` keeps following APP_REQUIRE_HTTPS.

Startup-only validation lives in ``validate_at_boot()``: create_app() calls it
so a misconfiguration fails the boot, while merely importing a module (or
running a script with a partial environment) no longer raises at import time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_TRUTHY = ("1", "true", "yes")

DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
DEFAULT_MIN_FREE_DISK_BYTES = 500 * 1024 * 1024


def _env_str(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the backend's environment-driven configuration."""

    cors_origins_raw: str  # APP_CORS_ORIGINS, comma-separated
    auth_email: str  # APP_AUTH_EMAIL — admin bootstrap identity
    auth_password: str  # APP_AUTH_PASSWORD — admin bootstrap password
    require_https: bool  # APP_REQUIRE_HTTPS — 426 plain-HTTP user routes + Secure cookie
    max_upload_bytes: int  # APP_MAX_UPLOAD_BYTES — per-image upload cap
    min_free_disk_bytes: int  # APP_MIN_FREE_DISK_BYTES — disk floor below which uploads 507
    data_dir: Path  # APP_DATA_DIR — image blobs, nonce DB, default control DB
    database_url: str  # DATABASE_URL — "" means the default SQLite file under data_dir
    openweather_api_key: str  # OPENWEATHER_API_KEY — weather proxy endpoints

    def cors_origins(self) -> list[str]:
        """Parse and validate APP_CORS_ORIGINS (required, no wildcard)."""
        if not self.cors_origins_raw:
            raise RuntimeError("APP_CORS_ORIGINS must be set.")
        origins = [o.strip().rstrip("/") for o in self.cors_origins_raw.split(",") if o.strip()]
        if not origins:
            raise RuntimeError("APP_CORS_ORIGINS is set but empty.")
        if "*" in origins:
            raise RuntimeError("Wildcard CORS origins are not allowed.")
        return origins

    def validate_at_boot(self) -> None:
        """Fail fast on misconfiguration; called once from create_app()."""
        self.cors_origins()
        if bool(self.auth_email) != bool(self.auth_password):
            raise RuntimeError(
                "APP_AUTH_EMAIL and APP_AUTH_PASSWORD must either both be set or both be unset."
            )
        if self.auth_password and len(self.auth_password) < 12:
            raise RuntimeError("APP_AUTH_PASSWORD must be at least 12 characters.")
        if self.max_upload_bytes <= 0:
            raise RuntimeError("APP_MAX_UPLOAD_BYTES must be greater than 0.")
        if self.min_free_disk_bytes < 0:
            raise RuntimeError("APP_MIN_FREE_DISK_BYTES must not be negative.")


def get_settings() -> Settings:
    """Fresh snapshot of the environment-driven settings."""
    return Settings(
        cors_origins_raw=_env_str("APP_CORS_ORIGINS"),
        auth_email=_env_str("APP_AUTH_EMAIL"),
        auth_password=_env_str("APP_AUTH_PASSWORD"),
        require_https=_env_str("APP_REQUIRE_HTTPS").lower() in _TRUTHY,
        max_upload_bytes=_env_int("APP_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES),
        min_free_disk_bytes=_env_int("APP_MIN_FREE_DISK_BYTES", DEFAULT_MIN_FREE_DISK_BYTES),
        data_dir=Path(_env_str("APP_DATA_DIR") or (_BACKEND_DIR / "data")).resolve(),
        database_url=_env_str("DATABASE_URL"),
        openweather_api_key=_env_str("OPENWEATHER_API_KEY"),
    )


def get_data_dir() -> Path:
    """Directory for image blobs and the replay-nonce DB (and the default control DB)."""
    return get_settings().data_dir
