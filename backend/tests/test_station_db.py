"""Tests for station database schema and persistence helpers."""

import sqlite3
from datetime import datetime, timezone

from config import station_db_path
from station_db import append_station_image, append_sensor_reading, ensure_station_db, latest_status_from_db


def test_append_station_image_records_upload_compatible_row(setup_station_dir):
    """Persisted image row contains the correct filename, type, size and timestamp."""
    data_dir, station_id = setup_station_dir
    db_path = station_db_path(data_dir, station_id)
    captured_at = datetime.now(timezone.utc).isoformat()

    append_station_image(
        db_path,
        filename="capture.jpg",
        content_type="image/jpeg",
        size_bytes=123,
        captured_at=captured_at,
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT filename, content_type, size_bytes, created_at FROM station_images"
        ).fetchone()

    assert row == ("capture.jpg", "image/jpeg", 123, captured_at)


def test_append_sensor_reading_records_history_row(setup_station_dir):
    """Persisted sensor row contains all fields with correct values."""
    data_dir, station_id = setup_station_dir
    db_path = station_db_path(data_dir, station_id)
    captured_at = datetime.now(timezone.utc).isoformat()

    append_sensor_reading(
        db_path,
        captured_at,
        {
            "temperature": 21.5,
            "humidity": 58,
            "pressure": 1012,
            "battery": 87,
            "wind_speed": 4.2,
            "wind_direction": 225,
            "visibility": 9.5,
            "uv_index": 3,
            "dew_point": 13.1,
            "feels_like": 20.9,
        },
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT timestamp, temperature, humidity, pressure, battery, wind_speed,
                   wind_direction, visibility, uv_index, dew_point, feels_like
            FROM sensor_history
            """
        ).fetchone()

    assert row == (captured_at, 21.5, 58, 1012, 87, 4.2, 225, 9.5, 3, 13.1, 20.9)


def test_append_sparse_sensor_log_records_nullable_history_row(setup_station_dir):
    data_dir, station_id = setup_station_dir
    db_path = station_db_path(data_dir, station_id)

    append_sensor_reading(
        db_path,
        "2026-05-24T14:30:00Z",
        {
            "voltage": 3.9,
            "firmware_version": "openmv-test",
            "next_start": "2026-05-24T15:00:00Z",
            "camera_name": "front",
            "wake_reason": "timer",
        },
        next_online="2026-05-24T15:00:00Z",
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT timestamp, temperature, battery, voltage, firmware_version,
                   next_start, camera_name, wake_reason, next_online
            FROM sensor_history
            """
        ).fetchone()

    assert row == (
        "2026-05-24T14:30:00Z",
        None,
        None,
        3.9,
        "openmv-test",
        "2026-05-24T15:00:00Z",
        "front",
        "timer",
        "2026-05-24T15:00:00Z",
    )


def test_ensure_station_db_migrates_required_sensor_columns_to_nullable(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE sensor_history (
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
        connection.execute(
            """
            INSERT INTO sensor_history (
                timestamp, temperature, humidity, pressure, battery,
                wind_speed, wind_direction, visibility, uv_index, dew_point, feels_like
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-05-24T14:00:00Z", 21.5, 58, 1012, 87, 4.2, 225, 9.5, 3, 13.1, 20.9),
        )
        connection.commit()

    ensure_station_db(db_path)
    append_sensor_reading(db_path, "2026-05-24T14:30:00Z", {"voltage": 3.9})

    with sqlite3.connect(db_path) as connection:
        columns = {row[1]: row for row in connection.execute("PRAGMA table_info(sensor_history)")}
        sparse_row = connection.execute(
            "SELECT temperature, voltage FROM sensor_history WHERE timestamp = ?",
            ("2026-05-24T14:30:00Z",),
        ).fetchone()
        legacy_count = connection.execute("SELECT COUNT(*) FROM sensor_history").fetchone()[0]

    assert columns["temperature"][3] == 0
    assert "firmware_version" in columns
    assert sparse_row == (None, 3.9)
    assert legacy_count == 2


def test_station_db_indexes_sensor_timestamps(setup_station_dir):
    """Sensor history reads use a timestamp index for latest and windowed queries."""
    data_dir, station_id = setup_station_dir
    db_path = station_db_path(data_dir, station_id)

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = ?",
            ("idx_sensor_history_timestamp",),
        ).fetchone()

    assert row == ("idx_sensor_history_timestamp",)


def test_latest_status_uses_latest_db_timestamp_and_next_online(setup_station_dir):
    data_dir, station_id = setup_station_dir
    db_path = station_db_path(data_dir, station_id)

    append_station_image(
        db_path,
        filename="capture.jpg",
        content_type="image/jpeg",
        size_bytes=123,
        captured_at="2026-05-23T12:00:00Z",
        next_online="2026-05-23T12:30:00Z",
    )
    append_sensor_reading(
        db_path,
        "2026-05-23T12:05:00Z",
        {
            "temperature": 21.5,
            "humidity": 58,
            "pressure": 1012,
            "battery": 87,
            "wind_speed": 4.2,
            "wind_direction": 225,
            "visibility": 9.5,
            "uv_index": 3,
            "dew_point": 13.1,
            "feels_like": 20.9,
        },
        next_online="2026-05-23T12:35:00Z",
    )

    capture, battery, last_online, next_online = latest_status_from_db(db_path, station_id)

    assert capture == {
        "timestamp": "2026-05-23T12:00:00Z",
        "url": f"/stations/{station_id}/images/capture.jpg",
    }
    assert battery == 87
    assert last_online == "2026-05-23T12:05:00Z"
    assert next_online == "2026-05-23T12:35:00Z"
