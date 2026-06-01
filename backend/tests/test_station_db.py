"""Tests for station database schema and persistence helpers."""

import json
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


def test_append_sensor_reading_stores_metrics_as_json(setup_station_dir):
    """A sensor row stores the metrics bag verbatim as JSON next to its timestamp."""
    data_dir, station_id = setup_station_dir
    db_path = station_db_path(data_dir, station_id)
    captured_at = datetime.now(timezone.utc).isoformat()
    metrics = {"temperature": 21.5, "humidity": 58, "pressure": 1012, "battery": 87, "reception": 73}

    append_sensor_reading(db_path, captured_at, metrics, next_online="2026-05-24T15:00:00Z")

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT timestamp, next_online, metrics FROM sensor_history"
        ).fetchone()

    assert row[0] == captured_at
    assert row[1] == "2026-05-24T15:00:00Z"
    assert json.loads(row[2]) == metrics


def test_append_sparse_sensor_reading_stores_only_given_metrics(setup_station_dir):
    """A reading with only a few fields stores exactly those — nothing is invented."""
    data_dir, station_id = setup_station_dir
    db_path = station_db_path(data_dir, station_id)
    metrics = {"voltage": 3.9, "firmwareVersion": "openmv-test", "cameraName": "front"}

    append_sensor_reading(
        db_path, "2026-05-24T14:30:00Z", metrics, next_online="2026-05-24T15:00:00Z"
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT timestamp, next_online, metrics FROM sensor_history"
        ).fetchone()

    assert row[0] == "2026-05-24T14:30:00Z"
    assert row[1] == "2026-05-24T15:00:00Z"
    assert json.loads(row[2]) == metrics


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
            "firmwareVersion": "openmv-1.2.0",
            "wakeReason": "timer",
        },
        next_online="2026-05-23T12:35:00Z",
    )

    status = latest_status_from_db(db_path, station_id)

    assert status.capture == {
        "timestamp": "2026-05-23T12:00:00Z",
        "url": f"/stations/{station_id}/images/capture.jpg",
    }
    assert status.battery == 87
    assert status.last_online == "2026-05-23T12:05:00Z"
    assert status.next_online == "2026-05-23T12:35:00Z"
    assert status.firmware_version == "openmv-1.2.0"
    assert status.wake_reason == "timer"
