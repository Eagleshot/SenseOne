"""Pytest configuration and fixtures."""

import pytest
import tempfile
import sqlite3
import gc
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

from config import ensure_station_dir, write_station_config
from models import AppConfig


@pytest.fixture
def tmp_data_dir():
    """Create a temporary data directory for tests."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        yield tmpdir
    finally:
        gc.collect()
        shutil.rmtree(tmpdir)


@pytest.fixture
def sample_station_id():
    """Return a sample station ID."""
    return "test-station"


@pytest.fixture
def sample_config():
    """Return a sample AppConfig."""
    return AppConfig(
        title="Test Station",
        description="A test station",
        lat=47.5,
        lon=8.5,
        alt=1000,
        location="Test Location",
        country="Test Country",
        country_emoji="ðŸ³ï¸",
        station_start_time="06:00",
        station_stop_time="20:00",
        capture_interval_minutes=30,
    )


@pytest.fixture
def setup_station_dir(tmp_data_dir, sample_station_id, sample_config):
    """Set up a test station directory with database and config."""
    ensure_station_dir(tmp_data_dir, sample_station_id)
    write_station_config(tmp_data_dir, sample_station_id, sample_config)
    return tmp_data_dir, sample_station_id


@pytest.fixture
def station_with_sample_images(setup_station_dir):
    """Set up station with sample image records."""
    data_dir, station_id = setup_station_dir
    
    # Add some sample image records to database
    from config import station_db_path
    db_path = station_db_path(data_dir, station_id)
    
    now = datetime.now(timezone.utc)
    with sqlite3.connect(db_path) as conn:
        for i in range(5):
            timestamp = (now - timedelta(hours=i)).isoformat()
            conn.execute(
                """
                INSERT INTO station_images (filename, content_type, size_bytes, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (f"{i}-test.jpg", "image/jpeg", 1000 + i * 100, timestamp),
            )
        conn.commit()
    
    return data_dir, station_id


@pytest.fixture
def station_with_history(setup_station_dir):
    """Set up station with sample sensor history."""
    data_dir, station_id = setup_station_dir
    
    from config import station_db_path
    db_path = station_db_path(data_dir, station_id)
    
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
    
    return data_dir, station_id


