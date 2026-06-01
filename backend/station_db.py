"""SQLite persistence for station image and sensor data.

Sensor readings are stored as a flat `metrics` JSON blob keyed by the
measurement name the device sent (e.g. ``temperature``, ``battery``,
``reception``). Nothing about the set of measurements is fixed in the schema,
so a station can report any field without a migration. The only sensor values
the server reads structurally are the timestamp, the scheduling hint
(``next_online``), and the values surfaced on the station status —
``battery``, ``firmwareVersion`` and ``wakeReason`` — pulled from the latest
reading via ``json_extract``.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils import iso_utc, parse_iso_timestamp

_SENSOR_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    next_online TEXT,
    metrics TEXT NOT NULL DEFAULT '{}'
)
"""

def _dump_metrics(metrics: dict) -> str:
    return json.dumps(metrics, separators=(",", ":"), allow_nan=False)


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


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
    metrics: dict,
    next_online: str | None = None,
) -> None:
    """Insert a station sensor reading. `metrics` is stored verbatim as JSON."""
    ensure_station_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO sensor_history (timestamp, next_online, metrics) VALUES (?, ?, ?)",
            (timestamp, next_online, _dump_metrics(metrics)),
        )
        connection.commit()


def history_from_db(db_path: Path, station_id: str, hours: int) -> list[dict[str, object]]:
    """Load sensor history rows from a station DB as flat {timestamp, **metrics} dicts."""
    if not db_path.exists():
        return []
    ensure_station_db(db_path)

    cutoff = iso_utc(datetime.now(timezone.utc) - timedelta(hours=hours))
    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT timestamp, metrics
                FROM sensor_history
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (cutoff,),
            ).fetchall()
    except sqlite3.Error as exc:
        logging.warning("Failed to read station history for %s: %s", station_id, exc)
        return []

    readings: list[dict[str, object]] = []
    for row in rows:
        metrics = json.loads(row["metrics"] or "{}")
        readings.append({"timestamp": row["timestamp"], **metrics})
    return readings


def _coerce_battery(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class StationStatus:
    """Latest runtime status for a station, derived from its SQLite data."""

    capture: dict | None = None
    battery: int | None = None
    last_online: str | None = None
    next_online: str | None = None
    firmware_version: str | None = None
    wake_reason: str | None = None


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def latest_status_from_db(db_path: Path, station_id: str) -> StationStatus:
    """Return latest image, battery, firmware, wake reason, and online times.

    ``battery``, ``firmwareVersion`` and ``wakeReason`` are read from the most
    recent sensor reading's metrics via ``json_extract``; everything else in
    the metrics blob is opaque to the server.
    """
    if not db_path.exists():
        return StationStatus()
    ensure_station_db(db_path)

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            image_row = connection.execute(
                "SELECT filename, created_at, next_online FROM station_images ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            sensor_row = connection.execute(
                "SELECT timestamp, next_online, "
                "json_extract(metrics, '$.battery') AS battery, "
                "json_extract(metrics, '$.firmwareVersion') AS firmware_version, "
                "json_extract(metrics, '$.wakeReason') AS wake_reason "
                "FROM sensor_history ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        logging.warning("Failed to read station status for %s: %s", station_id, exc)
        return StationStatus()

    capture = (
        {"timestamp": image_row["created_at"], "url": f"/stations/{station_id}/images/{image_row['filename']}"}
        if image_row else None
    )

    latest_timestamp = None
    next_online = None
    for row, timestamp_key in ((image_row, "created_at"), (sensor_row, "timestamp")):
        if row is None:
            continue
        parsed = parse_iso_timestamp(row[timestamp_key])
        if parsed is None:
            continue
        if latest_timestamp is None or parsed > latest_timestamp or (parsed == latest_timestamp and row["next_online"]):
            latest_timestamp = parsed
            next_online = row["next_online"]

    return StationStatus(
        capture=capture,
        battery=(None if sensor_row is None else _coerce_battery(sensor_row["battery"])),
        last_online=(iso_utc(latest_timestamp) if latest_timestamp else None),
        next_online=next_online,
        firmware_version=(None if sensor_row is None else _str_or_none(sensor_row["firmware_version"])),
        wake_reason=(None if sensor_row is None else _str_or_none(sensor_row["wake_reason"])),
    )
