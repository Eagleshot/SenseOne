"""Station queries built on the existing filesystem and per-station SQLite files."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import camera_db_path, read_camera_config
from constants import DEFAULT_ONLINE_THRESHOLD_MINUTES, NEXT_ONLINE_STATUS_BUFFER_MINUTES
from models import AppConfig
from station_db import history_from_db, image_captures_from_db, latest_battery_from_db
from utils import humanize_camera_id, iso_utc, parse_iso_timestamp, sanitize_camera_id


def list_station_ids(base_dir: Path) -> list[str]:
    """Get ordered list of station IDs from the data directory."""
    if not base_dir.exists():
        return []

    seen: set[str] = set()
    station_ids: list[str] = []
    for child in sorted(base_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        station_id = sanitize_camera_id(child.name)
        if station_id not in seen:
            station_ids.append(station_id)
            seen.add(station_id)
    return station_ids


def image_captures(base_dir: Path, station_id: str, count: int) -> list[dict[str, str]] | None:
    """Load recent image captures for a station."""
    return image_captures_from_db(camera_db_path(base_dir, station_id), station_id, count)


def sensor_history(base_dir: Path, station_id: str, hours: int) -> list[dict[str, object]] | None:
    """Load sensor history for a station."""
    return history_from_db(camera_db_path(base_dir, station_id), station_id, hours)


def latest_battery(base_dir: Path, station_id: str) -> int | None:
    """Load the latest battery reading for a station."""
    return latest_battery_from_db(camera_db_path(base_dir, station_id), station_id)


def latest_capture(base_dir: Path, station_id: str) -> tuple[datetime, str] | None:
    """Get the latest image capture for a station."""
    captures = image_captures(base_dir, station_id, count=1)
    if not captures:
        return None

    latest = captures[-1]
    timestamp = parse_iso_timestamp(latest.get("timestamp"))
    url = latest.get("url")
    if timestamp is None or not isinstance(url, str):
        return None
    return timestamp, url


def station_status(base_dir: Path, station_id: str, config: AppConfig) -> dict[str, object]:
    """Get the current online/image status for a station."""
    capture = latest_capture(base_dir, station_id)
    current_image = capture[1] if capture else None
    last_update = None
    next_update = None
    is_online = False
    now = datetime.now(timezone.utc)

    if capture:
        captured_at, _ = capture
        last_update = iso_utc(captured_at)
        next_update = iso_utc(captured_at + timedelta(minutes=config.capture_interval_minutes))
        threshold_minutes = max(config.capture_interval_minutes * 2, DEFAULT_ONLINE_THRESHOLD_MINUTES)
        is_online = (now - captured_at).total_seconds() <= threshold_minutes * 60

    next_online_at = parse_iso_timestamp(config.next_online)
    if next_online_at is not None:
        is_online = now <= next_online_at + timedelta(minutes=NEXT_ONLINE_STATUS_BUFFER_MINUTES)

    return {
        "is_online": is_online,
        "current_image": current_image,
        "last_update": config.last_online or last_update,
        "next_update": config.next_online or next_update,
    }


def station_summary(
    base_dir: Path,
    station_id: str,
    config: AppConfig | None = None,
    status: dict | None = None,
) -> dict[str, object]:
    """Get summary data for a station."""
    config = config or read_camera_config(base_dir, station_id)
    status = status or station_status(base_dir, station_id, config)
    return {
        "id": station_id,
        "name": config.title or humanize_camera_id(station_id),
        "location": config.location,
        "country": config.country,
        "country_emoji": config.country_emoji,
        "coordinates": {
            "lat": config.lat,
            "lng": config.lon,
            "altitude": config.alt,
        },
        "is_public": config.is_public,
        "is_online": status["is_online"],
    }


def station_detail(base_dir: Path, station_id: str) -> dict[str, object]:
    """Get detailed data for a station."""
    config = read_camera_config(base_dir, station_id)
    status = station_status(base_dir, station_id, config)
    return {
        **station_summary(base_dir, station_id, config=config, status=status),
        "description": config.description,
        "battery": latest_battery(base_dir, station_id),
        "current_image": status["current_image"],
        "last_update": status["last_update"],
        "next_update": status["next_update"],
    }
