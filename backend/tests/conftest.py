"""Pytest configuration and fixtures."""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from config import ensure_camera_dir, write_camera_config
from models import AppConfig


@pytest.fixture
def tmp_data_dir():
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_camera_id():
    """Return a sample camera ID."""
    return "test-camera"


@pytest.fixture
def sample_config():
    """Return a sample AppConfig."""
    return AppConfig(
        title="Test Camera",
        description="A test camera",
        lat=47.5,
        lon=8.5,
        alt=1000,
        location="Test Location",
        country="Test Country",
        country_emoji="🏳️",
        camera_start_time="06:00",
        camera_stop_time="20:00",
        capture_interval_minutes=30,
    )


@pytest.fixture
def setup_camera_dir(tmp_data_dir, sample_camera_id, sample_config):
    """Set up a test camera directory with database and config."""
    ensure_camera_dir(tmp_data_dir, sample_camera_id)
    write_camera_config(tmp_data_dir, sample_camera_id, sample_config)
    return tmp_data_dir, sample_camera_id


@pytest.fixture
def camera_with_sample_images(setup_camera_dir):
    """Set up camera with sample image records."""
    data_dir, camera_id = setup_camera_dir
    
    # Add some sample image records to database
    from config import camera_db_path
    db_path = camera_db_path(data_dir, camera_id)
    
    now = datetime.now(timezone.utc)
    with sqlite3.connect(db_path) as conn:
        for i in range(5):
            timestamp = (now - timedelta(hours=i)).isoformat()
            conn.execute(
                """
                INSERT INTO camera_images (filename, content_type, size_bytes, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (f"{i}-test.jpg", "image/jpeg", 1000 + i * 100, timestamp),
            )
        conn.commit()
    
    return data_dir, camera_id


@pytest.fixture
def camera_with_history(setup_camera_dir):
    """Set up camera with sample sensor history."""
    data_dir, camera_id = setup_camera_dir
    
    from config import camera_db_path
    db_path = camera_db_path(data_dir, camera_id)
    
    now = datetime.now(timezone.utc)
    with sqlite3.connect(db_path) as conn:
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            conn.execute(
                """
                INSERT INTO sensor_history
                (timestamp, temperature, humidity, pressure, battery, wind_speed, 
                 wind_direction, visibility, uv_index, dew_point, feels_like)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    20.0 + i * 0.5,  # temperature
                    65 - i,  # humidity
                    1013,  # pressure
                    95 - i,  # battery
                    5.0 + i * 0.1,  # wind_speed
                    180,  # wind_direction
                    10.0,  # visibility
                    5 + i,  # uv_index
                    15.0,  # dew_point
                    19.0,  # feels_like
                ),
            )
        conn.commit()
    
    return data_dir, camera_id
