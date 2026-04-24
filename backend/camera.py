"""Camera-related operations and data processing."""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils import (
    parse_embedded_timestamp,
    parse_iso_timestamp,
    iso_utc,
    humanize_camera_id,
    sanitize_camera_id,
)
from config import (
    camera_dir,
    camera_db_path,
    read_camera_config,
)
from models import AppConfig
from constants import DEFAULT_ONLINE_THRESHOLD_MINUTES

try:
    from mock_data import WEBCAM_SEED
except ImportError:
    WEBCAM_SEED = []


def all_camera_ids(base_dir: Path) -> list[str]:
    """Get ordered list of all camera IDs."""
    ordered_ids: list[str] = []
    seen: set[str] = set()

    for item in WEBCAM_SEED:
        normalized = sanitize_camera_id(str(item.get("id") or ""))
        if normalized in seen:
            continue
        ordered_ids.append(normalized)
        seen.add(normalized)

    if base_dir.exists():
        for child in sorted(base_dir.iterdir(), key=lambda path: path.name):
            if not child.is_dir():
                continue
            normalized = sanitize_camera_id(child.name)
            if normalized in seen:
                continue
            ordered_ids.append(normalized)
            seen.add(normalized)

    return ordered_ids


def _build_timeline_items(items: list[tuple[str, Path]], camera_id: str, count: int) -> list[dict[str, str]]:
    """Build timeline items from a list of (filename, path) tuples."""
    timeline_items: list[tuple[datetime, bool, dict[str, str]]] = []
    for filename, path in items:
        if not path.is_file():
            continue
        embedded_timestamp = parse_embedded_timestamp(filename)
        timestamp = embedded_timestamp or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        timeline_items.append(
            (
                timestamp,
                embedded_timestamp is not None,
                {
                    "timestamp": iso_utc(timestamp),
                    "url": f"/stations/{camera_id}/images/{filename}",
                },
            )
        )
    if not timeline_items:
        return []
    if any(item[1] for item in timeline_items):
        timeline_items = [item for item in timeline_items if item[1]]
    timeline_items.sort(key=lambda item: item[0])
    if len(timeline_items) > count:
        timeline_items = timeline_items[-count:]
    return [item[2] for item in timeline_items]


def timeline_from_camera_db(base_dir: Path, camera_id: str, count: int) -> list[dict[str, str]] | None:
    """Load image timeline from database."""
    db_path = camera_db_path(base_dir, camera_id)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT filename, created_at
                FROM camera_images
                """,
            ).fetchall()
    except sqlite3.Error as exc:
        logging.warning("Failed to read camera timeline for %s: %s", camera_id, exc)
        return None

    if not rows:
        return None

    images_dir = camera_dir(base_dir, camera_id) / "images"
    # Create items with database-resolved timestamps
    items = []
    for row in rows:
        filename = row["filename"]
        image_path = images_dir / filename
        items.append((filename, image_path))
    
    result = _build_timeline_items(items, camera_id, count)
    return result if result else None


def timeline_from_image_dir(base_dir: Path, camera_id: str, count: int) -> list[dict[str, str]]:
    """Load image timeline from filesystem directory."""
    images_dir = camera_dir(base_dir, camera_id) / "images"
    if not images_dir.exists():
        return []

    files = [path for path in images_dir.iterdir() if path.is_file()]
    if not files:
        return []

    items = [(path.name, path) for path in files]
    return _build_timeline_items(items, camera_id, count)


def history_from_camera_db(base_dir: Path, camera_id: str, hours: int) -> list[dict[str, object]] | None:
    """Load sensor history from database."""
    db_path = camera_db_path(base_dir, camera_id)
    if not db_path.exists():
        return None

    cutoff = iso_utc(datetime.now(timezone.utc) - timedelta(hours=hours))
    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    timestamp,
                    temperature,
                    humidity,
                    pressure,
                    battery,
                    wind_speed,
                    wind_direction,
                    visibility,
                    uv_index,
                    dew_point,
                    feels_like
                FROM sensor_history
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (cutoff,),
            ).fetchall()
    except sqlite3.Error as exc:
        logging.warning("Failed to read camera history for %s: %s", camera_id, exc)
        return None

    if not rows:
        return []

    return [
        {
            "timestamp": row["timestamp"],
            "temperature": row["temperature"],
            "humidity": row["humidity"],
            "pressure": row["pressure"],
            "battery": row["battery"],
            "windSpeed": row["wind_speed"],
            "windDirection": row["wind_direction"],
            "visibility": row["visibility"],
            "uvIndex": row["uv_index"],
            "dewPoint": row["dew_point"],
            "feelsLike": row["feels_like"],
        }
        for row in rows
    ]


def chart_data_sources_from_camera_db(base_dir: Path, camera_id: str) -> list[dict[str, object]] | None:
    """Load chart data sources from the station database."""
    db_path = camera_db_path(base_dir, camera_id)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    source_id,
                    label,
                    icon_key,
                    color_value
                FROM chart_data_sources
                ORDER BY label COLLATE NOCASE ASC
                """
            ).fetchall()
    except sqlite3.Error as exc:
        logging.warning("Failed to read chart data sources for %s: %s", camera_id, exc)
        return None

    if not rows:
        return []

    sources: list[dict[str, object]] = []
    for row in rows:
        sources.append(
            {
                "id": row["source_id"],
                "label": row["label"],
                "icon": row["icon_key"],
                "color": row["color_value"],
            }
        )
    return sources


def latest_camera_battery(base_dir: Path, camera_id: str) -> int | None:
    """Load the latest battery reading from the station database."""
    db_path = camera_db_path(base_dir, camera_id)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT battery
                FROM sensor_history
                ORDER BY timestamp DESC
                LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error as exc:
        logging.warning("Failed to read latest camera battery for %s: %s", camera_id, exc)
        return None

    if row is None:
        return None

    return row["battery"]


def latest_camera_capture(base_dir: Path, camera_id: str) -> tuple[datetime, str] | None:
    """Get the latest image capture for a camera."""
    timeline = timeline_from_camera_db(base_dir, camera_id, count=1)
    if timeline is None:
        timeline = timeline_from_image_dir(base_dir, camera_id, count=1)
    if not timeline:
        return None

    latest_item = timeline[-1]
    timestamp = parse_iso_timestamp(latest_item.get("timestamp"))
    url = latest_item.get("url")
    if timestamp is None or not isinstance(url, str):
        return None
    return timestamp, url


def camera_status(base_dir: Path, camera_id: str, config: AppConfig) -> dict[str, object]:
    """Get the current status of a camera."""
    latest_capture = latest_camera_capture(base_dir, camera_id)
    current_image = latest_capture[1] if latest_capture is not None else None

    if any(value is not None for value in (config.is_online, config.last_online, config.next_online)):
        derived_last_update = None
        derived_next_update = None
        derived_is_online = False

        if latest_capture is not None:
            last_timestamp, _ = latest_capture
            derived_last_update = iso_utc(last_timestamp)
            derived_next_update = iso_utc(last_timestamp + timedelta(minutes=config.capture_interval_minutes))
            threshold_minutes = max(config.capture_interval_minutes * 2, DEFAULT_ONLINE_THRESHOLD_MINUTES)
            age_seconds = (datetime.now(timezone.utc) - last_timestamp).total_seconds()
            derived_is_online = age_seconds <= threshold_minutes * 60

        return {
            "isOnline": config.is_online if config.is_online is not None else derived_is_online,
            "currentImage": current_image,
            "lastUpdate": config.last_online or derived_last_update,
            "nextUpdate": config.next_online or derived_next_update,
        }

    if latest_capture is None:
        return {
            "isOnline": False,
            "currentImage": None,
            "lastUpdate": None,
            "nextUpdate": None,
        }

    last_timestamp, current_image = latest_capture
    threshold_minutes = max(config.capture_interval_minutes * 2, DEFAULT_ONLINE_THRESHOLD_MINUTES)
    age_seconds = (datetime.now(timezone.utc) - last_timestamp).total_seconds()
    return {
        "isOnline": age_seconds <= threshold_minutes * 60,
        "currentImage": current_image,
        "lastUpdate": iso_utc(last_timestamp),
        "nextUpdate": iso_utc(last_timestamp + timedelta(minutes=config.capture_interval_minutes)),
    }


def camera_summary(base_dir: Path, camera_id: str) -> dict[str, object]:
    """Get summary data for a camera."""
    config = read_camera_config(base_dir, camera_id)
    name = config.title or humanize_camera_id(camera_id)
    battery = latest_camera_battery(base_dir, camera_id)
    summary = {
        "id": camera_id,
        "name": name,
        "location": config.location,
        "country": config.country,
        "battery": battery,
        "countryEmoji": config.country_emoji,
        "coordinates": {
            "lat": config.lat,
            "lng": config.lon,
            "altitude": config.alt,
        },
    }
    summary["isOnline"] = camera_status(base_dir, camera_id, config)["isOnline"]
    return summary


def camera_detail(base_dir: Path, camera_id: str) -> dict[str, object]:
    """Get detailed data for a camera."""
    config = read_camera_config(base_dir, camera_id)
    detail = camera_summary(base_dir, camera_id)
    status = camera_status(base_dir, camera_id, config)

    detail.update(
        {
            "description": config.description,
            "country": config.country,
            "countryEmoji": config.country_emoji,
            "currentImage": status["currentImage"],
            "isOnline": status["isOnline"],
            "lastUpdate": status["lastUpdate"],
            "nextUpdate": status["nextUpdate"],
        }
    )
    return detail
