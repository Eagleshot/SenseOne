"""Camera configuration management."""

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from constants import CAMERA_CONFIG_FILENAME, CAMERA_DB_FILENAME
from models import AppConfig
from utils import iso_utc, sanitize_camera_id

try:
    from mock_data import WEBCAM_SEED
except ImportError:
    WEBCAM_SEED = []


CONFIG_FIELDS = (
    "title",
    "description",
    "lat",
    "lon",
    "alt",
    "location",
    "country",
    "country_emoji",
    "is_online",
    "last_online",
    "next_online",
    "camera_start_time",
    "camera_stop_time",
    "use_sunrise_sunset",
    "capture_interval_minutes",
)


def get_data_dir() -> Path:
    """Get data directory from environment."""
    base_dir = Path(__file__).resolve().parent
    return Path(os.getenv("APP_DATA_DIR") or (base_dir / "data")).resolve()


def camera_seed_defaults(camera_id: str) -> dict[str, object]:
    """Get default camera configuration from seed data."""
    normalized = sanitize_camera_id(camera_id)
    for item in WEBCAM_SEED:
        if sanitize_camera_id(str(item.get("id") or "")) != normalized:
            continue

        coordinates = item.get("coordinates") or {}
        now = datetime.now(timezone.utc)
        last_online = now - timedelta(minutes=int(item.get("lastUpdateMinutesAgo") or 0))
        next_online = now + timedelta(minutes=int(item.get("nextUpdateMinutesIn") or 0))
        return {
            "title": str(item.get("name") or ""),
            "description": str(item.get("description") or ""),
            "lat": coordinates.get("lat", 0.0),
            "lon": coordinates.get("lng", 0.0),
            "alt": coordinates.get("altitude", 0.0),
            "location": str(item.get("location") or ""),
            "country": str(item.get("country") or ""),
            "country_emoji": str(item.get("countryEmoji") or ""),
            "is_online": bool(item.get("isOnline")),
            "last_online": iso_utc(last_online),
            "next_online": iso_utc(next_online),
        }

    return {}


def default_camera_config(camera_id: str) -> AppConfig:
    """Get default configuration for a camera."""
    return AppConfig(**camera_seed_defaults(camera_id))


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

    parsed.pop("camera_id", None)
    defaults = default_camera_config(camera_id).model_dump()
    defaults.update({k: v for k, v in parsed.items() if k in CONFIG_FIELDS})
    try:
        return AppConfig(**defaults)
    except ValidationError as exc:
        logging.error("Camera config for %s failed validation: %s", camera_id, exc)
        return default_camera_config(camera_id)


def write_camera_config(base_dir: Path, camera_id: str, values: AppConfig) -> None:
    """Write camera configuration to file."""
    ensure_camera_dir(base_dir, camera_id)
    camera_config_path(base_dir, camera_id).write_text(
        camera_config_yaml_for_values(values),
        encoding="utf-8",
    )


def ensure_camera_dir(base_dir: Path, camera_id: str) -> None:
    """Ensure camera directory and database exist."""
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
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS camera_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL NOT NULL,
                humidity INTEGER NOT NULL,
                pressure INTEGER NOT NULL,
                battery INTEGER NOT NULL,
                wind_speed REAL NOT NULL,
                wind_direction INTEGER NOT NULL,
                visibility REAL NOT NULL,
                uv_index INTEGER NOT NULL,
                dew_point REAL NOT NULL,
                feels_like REAL NOT NULL
            )
            """
        )
        connection.commit()
