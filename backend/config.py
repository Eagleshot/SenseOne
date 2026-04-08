"""Camera configuration management."""

import logging
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

from models import AppConfig
from utils import iso_utc, to_yaml_value
from constants import CAMERA_CONFIG_FILENAME, CAMERA_DB_FILENAME

try:
    from mock_data import WEBCAM_SEED
except ImportError:
    WEBCAM_SEED = []


def get_data_dir() -> Path:
    """Get data directory from environment."""
    BASE_DIR = Path(__file__).resolve().parent
    return Path(os.getenv("APP_DATA_DIR") or (BASE_DIR / "data")).resolve()


def camera_seed_defaults(camera_id: str) -> dict[str, object]:
    """Get default camera configuration from seed data."""
    from utils import sanitize_camera_id

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


def camera_config_yaml_for_values(camera_id: str, values: AppConfig) -> str:
    """Generate YAML configuration from AppConfig values."""
    _ = camera_id
    return "\n".join(
        [
            f"title: {to_yaml_value(values.title)}",
            f"description: {to_yaml_value(values.description)}",
            f"lat: {values.lat}",
            f"lon: {values.lon}",
            f"alt: {values.alt}",
            f"location: {to_yaml_value(values.location)}",
            f"country: {to_yaml_value(values.country)}",
            f"country_emoji: {to_yaml_value(values.country_emoji)}",
            f"is_online: {'true' if values.is_online is True else 'false' if values.is_online is False else 'null'}",
            f"last_online: {to_yaml_value(values.last_online)}",
            f"next_online: {to_yaml_value(values.next_online)}",
            f"camera_start_time: {to_yaml_value(values.camera_start_time)}",
            f"camera_stop_time: {to_yaml_value(values.camera_stop_time)}",
            f"use_sunrise_sunset: {'true' if values.use_sunrise_sunset else 'false'}",
            f"capture_interval_minutes: {values.capture_interval_minutes}",
            "",
        ]
    )


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
    """Read camera configuration from file."""
    config_path = camera_config_path(base_dir, camera_id)
    if not config_path.exists():
        ensure_camera_dir(base_dir, camera_id)
        return default_camera_config(camera_id)

    try:
        text = config_path.read_text(encoding="utf-8")
        parsed: dict[str, object] = {}
        for line in text.splitlines():
            raw_line = line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue
            if ":" not in raw_line:
                continue
            key, raw_value = (part.strip() for part in raw_line.split(":", 1))
            value = raw_value.strip().strip("\"'")
            if key == "camera_id":
                continue
            if key in {"camera_start_time", "camera_stop_time"}:
                parsed[key] = value
            elif key == "use_sunrise_sunset":
                parsed[key] = value.lower() in {"1", "true", "yes", "on"}
            elif key == "capture_interval_minutes":
                parsed[key] = int(value)
            elif key in {"title", "description"}:
                parsed[key] = value
            elif key in {"lat", "lon", "alt"}:
                parsed[key] = float(value)
            elif key == "is_online":
                parsed[key] = value.lower() in {"1", "true", "yes", "on"} if value.lower() != "null" else None
            elif key in {"last_online", "next_online"}:
                parsed[key] = None if value.lower() == "null" else value
            elif key in {"location", "country", "country_emoji", "contry_emoji"}:
                parsed["country_emoji" if key == "contry_emoji" else key] = value
        defaults = default_camera_config(camera_id).model_dump()
        defaults.update(parsed)
        return AppConfig(**defaults)
    except (OSError, ValueError, TypeError) as exc:
        logging.error("Failed to read camera config for %s: %s", camera_id, exc)
        return default_camera_config(camera_id)


def write_camera_config(base_dir: Path, camera_id: str, values: AppConfig) -> None:
    """Write camera configuration to file."""
    ensure_camera_dir(base_dir, camera_id)
    camera_config_path(base_dir, camera_id).write_text(
        camera_config_yaml_for_values(camera_id, values),
        encoding="utf-8",
    )


def ensure_camera_dir(base_dir: Path, camera_id: str) -> None:
    """Ensure camera directory and database exist."""
    import sqlite3
    
    camera_root = camera_dir(base_dir, camera_id)
    images_dir = camera_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    config_file = camera_config_path(base_dir, camera_id)
    if not config_file.exists():
        config_file.write_text(camera_config_yaml_for_values(camera_id, default_camera_config(camera_id)), encoding="utf-8")

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
