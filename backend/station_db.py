"""SQLite persistence for station image and sensor data."""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils import iso_utc


def ensure_station_db(db_path: Path) -> None:
    """Create the per-station database schema if needed."""
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS station_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_images_created_at ON station_images(created_at)"
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


def image_captures_from_db(db_path: Path, station_id: str, count: int) -> list[dict[str, str]]:
    """Return recent image capture rows from a station DB, oldest-to-newest."""
    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT filename, created_at
                FROM station_images
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (count,),
            ).fetchall()
    except sqlite3.Error as exc:
        logging.warning("Failed to read station timeline for %s: %s", station_id, exc)
        return []

    return [
        {
            "timestamp": row["created_at"],
            "url": f"/stations/{station_id}/images/{row['filename']}",
        }
        for row in reversed(rows)
    ]


def append_station_image(
    db_path: Path,
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    captured_at: str,
) -> None:
    """Insert a stored station image row."""
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO station_images (filename, content_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (filename, content_type, size_bytes, captured_at),
        )
        connection.commit()


def append_sensor_reading(db_path: Path, timestamp: str, fields: dict) -> None:
    """Insert a station sensor reading row."""
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO sensor_history (
                timestamp, temperature, humidity, pressure, battery,
                wind_speed, wind_direction, visibility, uv_index, dew_point, feels_like
            ) VALUES (
                :timestamp, :temperature, :humidity, :pressure, :battery,
                :wind_speed, :wind_direction, :visibility, :uv_index, :dew_point, :feels_like
            )
            """,
            {"timestamp": timestamp, **fields},
        )
        connection.commit()


def history_from_db(db_path: Path, station_id: str, hours: int) -> list[dict[str, object]]:
    """Load sensor history rows from a station DB."""
    if not db_path.exists():
        return []

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
        logging.warning("Failed to read station history for %s: %s", station_id, exc)
        return []

    return [dict(row) for row in rows]


def latest_battery_from_db(db_path: Path, station_id: str) -> int | None:
    """Load the latest battery reading from a station DB."""
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
        logging.warning("Failed to read latest station battery for %s: %s", station_id, exc)
        return None

    return None if row is None else row["battery"]
