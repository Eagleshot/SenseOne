"""SQLite persistence for station image and sensor data."""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils import iso_utc, parse_iso_timestamp

SENSOR_HISTORY_COLUMNS = (
    "temperature",
    "humidity",
    "pressure",
    "battery",
    "wind_speed",
    "wind_direction",
    "visibility",
    "uv_index",
    "dew_point",
    "feels_like",
    "voltage",
    "device_temperature",
    "firmware_version",
    "next_start",
    "camera_name",
    "wake_reason",
)

_SENSOR_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    temperature REAL,
    humidity INTEGER,
    pressure INTEGER,
    battery INTEGER,
    wind_speed REAL,
    wind_direction INTEGER,
    visibility REAL,
    uv_index INTEGER,
    dew_point REAL,
    feels_like REAL,
    voltage REAL,
    device_temperature REAL,
    firmware_version TEXT,
    next_start TEXT,
    camera_name TEXT,
    wake_reason TEXT,
    next_online TEXT
)
"""


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def _sensor_history_needs_rebuild(connection: sqlite3.Connection) -> bool:
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(sensor_history)")}
    expected = {"id", "timestamp", "next_online", *SENSOR_HISTORY_COLUMNS}
    if not expected.issubset(columns):
        return True
    return any(columns[column][3] for column in SENSOR_HISTORY_COLUMNS)


def _rebuild_sensor_history(connection: sqlite3.Connection) -> None:
    existing = {row[1] for row in connection.execute("PRAGMA table_info(sensor_history)")}
    connection.execute("ALTER TABLE sensor_history RENAME TO sensor_history_old")
    connection.execute(_SENSOR_HISTORY_SCHEMA)
    copy_columns = [column for column in ("id", "timestamp", *SENSOR_HISTORY_COLUMNS, "next_online") if column in existing]
    quoted_columns = ", ".join(copy_columns)
    connection.execute(
        f"""
        INSERT INTO sensor_history ({quoted_columns})
        SELECT {quoted_columns}
        FROM sensor_history_old
        """
    )
    connection.execute("DROP TABLE sensor_history_old")


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
        _ensure_column(connection, "station_images", "next_online", "next_online TEXT")
        connection.execute(_SENSOR_HISTORY_SCHEMA)
        if _sensor_history_needs_rebuild(connection):
            _rebuild_sensor_history(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sensor_history_timestamp ON sensor_history(timestamp)"
        )
        connection.commit()


def image_captures_from_db(db_path: Path, station_id: str, count: int) -> list[dict[str, str]]:
    """Return recent image capture rows from a station DB, oldest-to-newest."""
    if not db_path.exists():
        return []
    ensure_station_db(db_path)

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
    next_online: str | None = None,
) -> None:
    """Insert a stored station image row."""
    ensure_station_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO station_images (filename, content_type, size_bytes, created_at, next_online)
            VALUES (?, ?, ?, ?, ?)
            """,
            (filename, content_type, size_bytes, captured_at, next_online),
        )
        connection.commit()


def append_sensor_reading(
    db_path: Path,
    timestamp: str,
    fields: dict,
    next_online: str | None = None,
) -> None:
    """Insert a station sensor reading row."""
    ensure_station_db(db_path)
    values = {column: fields.get(column) for column in SENSOR_HISTORY_COLUMNS}
    values["timestamp"] = timestamp
    values["next_online"] = next_online
    insert_columns = ("timestamp", *SENSOR_HISTORY_COLUMNS, "next_online")
    placeholders = ", ".join(f":{column}" for column in insert_columns)
    column_list = ", ".join(insert_columns)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            f"INSERT INTO sensor_history ({column_list}) VALUES ({placeholders})",
            values,
        )
        connection.commit()


def history_from_db(db_path: Path, station_id: str, hours: int) -> list[dict[str, object]]:
    """Load sensor history rows from a station DB."""
    if not db_path.exists():
        return []
    ensure_station_db(db_path)

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
                    feels_like,
                    voltage,
                    device_temperature,
                    firmware_version,
                    next_start,
                    camera_name,
                    wake_reason
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


def latest_status_from_db(
    db_path: Path, station_id: str
) -> tuple[dict | None, int | None, str | None, str | None]:
    """Return latest image, battery, last online, and next online in one DB connection."""
    if not db_path.exists():
        return None, None, None, None
    ensure_station_db(db_path)

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            image_row = connection.execute(
                "SELECT filename, created_at, next_online FROM station_images ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            battery_row = connection.execute(
                "SELECT timestamp, battery, next_online FROM sensor_history ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        logging.warning("Failed to read station status for %s: %s", station_id, exc)
        return None, None, None, None

    capture = (
        {"timestamp": image_row["created_at"], "url": f"/stations/{station_id}/images/{image_row['filename']}"}
        if image_row else None
    )

    latest_timestamp = None
    next_online = None
    for row, timestamp_key in ((image_row, "created_at"), (battery_row, "timestamp")):
        if row is None:
            continue
        parsed = parse_iso_timestamp(row[timestamp_key])
        if parsed is None:
            continue
        if latest_timestamp is None or parsed > latest_timestamp or (parsed == latest_timestamp and row["next_online"]):
            latest_timestamp = parsed
            next_online = row["next_online"]

    return (
        capture,
        (None if battery_row is None else battery_row["battery"]),
        (iso_utc(latest_timestamp) if latest_timestamp else None),
        next_online,
    )
