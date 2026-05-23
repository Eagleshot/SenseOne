"""Camera configuration management."""

import logging
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from constants import CAMERA_CONFIG_FILENAME, CAMERA_DB_FILENAME
from models import AppConfig


CONFIG_FIELDS = (
    "title",
    "description",
    "lat",
    "lon",
    "alt",
    "location",
    "country",
    "country_emoji",
    "is_public",
    "last_online",
    "next_online",
    "camera_start_time",
    "camera_stop_time",
    "use_sunrise_sunset",
    "capture_interval_minutes",
)

META_OWNER_KEY = "_owner"
META_DEVICE_HMAC_SECRET_KEY = "_device_hmac_secret_b64"
META_FIELDS = (META_OWNER_KEY, META_DEVICE_HMAC_SECRET_KEY)


def get_data_dir() -> Path:
    """Get data directory from environment."""
    base_dir = Path(__file__).resolve().parent
    return Path(os.getenv("APP_DATA_DIR") or (base_dir / "data")).resolve()


def default_camera_config(camera_id: str) -> AppConfig:
    """Get default configuration for a camera."""
    return AppConfig()


def camera_config_yaml_for_values(values: AppConfig) -> str:
    """Serialize AppConfig values to YAML."""
    payload = {field: getattr(values, field) for field in CONFIG_FIELDS}
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def camera_dir(base_dir: Path, camera_id: str) -> Path:
    """Get the directory path for a camera."""
    return base_dir / camera_id


def camera_db_path(base_dir: Path, camera_id: str) -> Path:
    """Get the database file path for a camera."""
    return camera_dir(base_dir, camera_id) / CAMERA_DB_FILENAME


def camera_config_path(base_dir: Path, camera_id: str) -> Path:
    """Get the configuration file path for a camera."""
    return camera_dir(base_dir, camera_id) / CAMERA_CONFIG_FILENAME


def read_camera_config(base_dir: Path, camera_id: str) -> AppConfig:
    """Read camera configuration from file. On read or parse failure, falls back to defaults."""
    config_path = camera_config_path(base_dir, camera_id)
    if not config_path.exists():
        ensure_camera_dir(base_dir, camera_id)
        return default_camera_config(camera_id)

    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        logging.error("Failed to read camera config for %s: %s", camera_id, exc)
        return default_camera_config(camera_id)

    try:
        parsed = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        logging.error("Failed to parse camera config for %s: %s", camera_id, exc)
        return default_camera_config(camera_id)

    if not isinstance(parsed, dict):
        logging.error("Camera config for %s is not a mapping; using defaults.", camera_id)
        return default_camera_config(camera_id)

    defaults = default_camera_config(camera_id).model_dump()
    defaults.update({k: v for k, v in parsed.items() if k in CONFIG_FIELDS})
    try:
        return AppConfig(**defaults)
    except ValidationError as exc:
        logging.error("Camera config for %s failed validation: %s", camera_id, exc)
        return default_camera_config(camera_id)


def _read_raw_yaml(base_dir: Path, camera_id: str) -> dict:
    """Read the raw YAML mapping for a camera, returning {} on any error."""
    config_path = camera_config_path(base_dir, camera_id)
    if not config_path.exists():
        return {}
    try:
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def write_camera_config(base_dir: Path, camera_id: str, values: AppConfig) -> None:
    """Write camera configuration to file, preserving server-managed meta fields."""
    ensure_camera_dir(base_dir, camera_id)
    existing = _read_raw_yaml(base_dir, camera_id)
    payload = {field: getattr(values, field) for field in CONFIG_FIELDS}
    for meta_key in META_FIELDS:
        if meta_key in existing:
            payload[meta_key] = existing[meta_key]
    camera_config_path(base_dir, camera_id).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def read_station_owner(base_dir: Path, camera_id: str) -> str | None:
    """Return the username that owns this station, or None if unowned."""
    value = _read_raw_yaml(base_dir, camera_id).get(META_OWNER_KEY)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def read_station_device_hmac_secret_b64(base_dir: Path, camera_id: str) -> str | None:
    """Return the base64url-encoded device HMAC secret for this station, or None."""
    value = _read_raw_yaml(base_dir, camera_id).get(META_DEVICE_HMAC_SECRET_KEY)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def write_station_meta(
    base_dir: Path,
    camera_id: str,
    *,
    owner: str | None = ...,
    device_hmac_secret_b64: str | None = ...,
) -> None:
    """Update server-managed meta fields without touching user-editable config."""
    ensure_camera_dir(base_dir, camera_id)
    existing = _read_raw_yaml(base_dir, camera_id)
    if not existing:
        existing = {field: getattr(default_camera_config(camera_id), field) for field in CONFIG_FIELDS}
    if owner is not ...:
        if owner is None:
            existing.pop(META_OWNER_KEY, None)
        else:
            existing[META_OWNER_KEY] = owner
    if device_hmac_secret_b64 is not ...:
        if device_hmac_secret_b64 is None:
            existing.pop(META_DEVICE_HMAC_SECRET_KEY, None)
        else:
            existing[META_DEVICE_HMAC_SECRET_KEY] = device_hmac_secret_b64
    camera_config_path(base_dir, camera_id).write_text(
        yaml.safe_dump(existing, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def ensure_camera_dir(base_dir: Path, camera_id: str) -> None:
    """Ensure camera directory and database exist."""
    from station_db import ensure_station_db

    camera_root = camera_dir(base_dir, camera_id)
    images_dir = camera_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    config_file = camera_config_path(base_dir, camera_id)
    if not config_file.exists():
        config_file.write_text(
            camera_config_yaml_for_values(default_camera_config(camera_id)),
            encoding="utf-8",
        )

    db_path = camera_db_path(base_dir, camera_id)
    ensure_station_db(db_path)
