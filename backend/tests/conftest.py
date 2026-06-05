"""Pytest fixtures.

Integration fixtures are backed by a throwaway SQLite database (TEST_DATABASE_URL,
defaulting to a temp file) — no server needed. Image blobs still go to a temp dir
on disk.
"""

import gc
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from models import AppConfig
from tests import _db


@pytest.fixture(scope="session")
def _engine():
    """Session-wide engine bound to the test DB, schema created from ORM metadata."""
    return _db.init_engine()


@pytest.fixture
def db(_engine, monkeypatch):
    """Fresh, empty database with the app engine pointed at it."""
    _db.reset_data()
    monkeypatch.setenv("DATABASE_URL", _db.TEST_DATABASE_URL)
    yield


@pytest.fixture
def tmp_data_dir():
    """Temp directory for image blobs (APP_DATA_DIR)."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        yield tmpdir
    finally:
        gc.collect()
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def sample_station_id():
    return "test-station"


@pytest.fixture
def sample_config():
    return AppConfig(
        title="Test Station",
        description="A test station",
        lat=47.5,
        lon=8.5,
        alt=1000,
        location="Test Location",
        country="Test Country",
        country_emoji="🏳️",
        station_start_time="06:00",
        station_stop_time="20:00",
        capture_interval_minutes=30,
    )


@pytest.fixture
def setup_station_dir(db, tmp_data_dir, sample_station_id, monkeypatch):
    """Create a public station row + temp blob dir. Returns (data_dir, station_id)."""
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    _db.create_station_row(
        sample_station_id,
        is_public=True,
        title="Test Station",
        location="Test Location",
        country="Test Country",
        country_emoji="🏳️",
        lat=47.5,
        lon=8.5,
        alt=1000,
    )
    return tmp_data_dir, sample_station_id


@pytest.fixture
def station_with_sample_images(setup_station_dir):
    """Station with 5 image rows: '<i>-test.jpg' captured i hours ago (newest = 0-test.jpg)."""
    data_dir, station_id = setup_station_dir
    now = datetime.now(timezone.utc)
    for i in range(5):
        _db.add_image(station_id, f"{i}-test.jpg", now - timedelta(hours=i), size_bytes=1000 + i * 100)
    return data_dir, station_id


@pytest.fixture
def station_with_history(setup_station_dir):
    """Station with 10 hourly sensor readings (latest battery = 95)."""
    data_dir, station_id = setup_station_dir
    now = datetime.now(timezone.utc)
    for i in range(10):
        _db.add_reading(
            station_id,
            now - timedelta(hours=i),
            {
                "temperature": 20.0 + i * 0.5,
                "humidity": 65 - i,
                "pressure": 1013,
                "battery": 95 - i,
                "reception": 80 - i,
            },
        )
    return data_dir, station_id
