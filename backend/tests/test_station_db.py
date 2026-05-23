"""Tests for station database schema and persistence helpers."""

import sqlite3
from datetime import datetime, timezone

from config import camera_db_path
from station_db import append_camera_image, append_sensor_reading


def test_append_camera_image_records_upload_compatible_row(setup_camera_dir):
    data_dir, camera_id = setup_camera_dir
    db_path = camera_db_path(data_dir, camera_id)
    captured_at = datetime.now(timezone.utc).isoformat()

    append_camera_image(
        db_path,
        filename="capture.jpg",
        content_type="image/jpeg",
        size_bytes=123,
        captured_at=captured_at,
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT filename, content_type, size_bytes, created_at FROM camera_images"
        ).fetchone()

    assert row == ("capture.jpg", "image/jpeg", 123, captured_at)


def test_append_sensor_reading_records_history_row(setup_camera_dir):
    data_dir, camera_id = setup_camera_dir
    db_path = camera_db_path(data_dir, camera_id)
    captured_at = datetime.now(timezone.utc).isoformat()

    append_sensor_reading(
        db_path,
        timestamp=captured_at,
        temperature=21.5,
        humidity=58,
        pressure=1012,
        battery=87,
        wind_speed=4.2,
        wind_direction=225,
        visibility=9.5,
        uv_index=3,
        dew_point=13.1,
        feels_like=20.9,
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
