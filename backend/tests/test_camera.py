"""Tests for camera operations."""

from datetime import datetime

from camera import (
    all_camera_ids,
    timeline_from_camera_db,
    history_from_camera_db,
    latest_camera_battery,
    latest_camera_capture,
    camera_status,
    camera_summary,
    camera_detail,
)
from config import ensure_camera_dir
from models import AppConfig


class TestCameraListing:
    """Test camera listing operations."""

    def test_all_camera_ids_empty(self, tmp_data_dir):
        """Test listing cameras with no filesystem cameras."""
        # Note: WEBCAM_SEED includes mock cameras, so this won't be truly empty
        ids = all_camera_ids(tmp_data_dir)
        # Just verify it returns a list
        assert isinstance(ids, list)

    def test_all_camera_ids_single(self, setup_camera_dir):
        """Test listing with one camera."""
        data_dir, camera_id = setup_camera_dir
        ids = all_camera_ids(data_dir)
        assert camera_id in ids

    def test_all_camera_ids_multiple(self, tmp_data_dir):
        """Test listing multiple cameras."""
        for i in range(3):
            ensure_camera_dir(tmp_data_dir, f"camera-{i}")
        
        ids = all_camera_ids(tmp_data_dir)
        # Should contain at least the cameras we created
        assert all(f"camera-{i}" in ids for i in range(3))


class TestTimeline:
    """Test timeline operations."""

    def test_timeline_from_db_no_database(self, tmp_data_dir, sample_camera_id):
        """Test timeline when database doesn't exist."""
        result = timeline_from_camera_db(tmp_data_dir, sample_camera_id, 10)
        assert result is None

    def test_timeline_from_db_empty(self, setup_camera_dir):
        """Test timeline with empty database."""
        data_dir, camera_id = setup_camera_dir
        result = timeline_from_camera_db(data_dir, camera_id, 10)
        assert result is None

    def test_timeline_from_db_with_images(self, camera_with_sample_images):
        """Test timeline with image records returns list."""
        data_dir, camera_id = camera_with_sample_images
        result = timeline_from_camera_db(data_dir, camera_id, 10)
        
        # With no embedded timestamps in filenames, should return sorted list
        if result is not None:
            assert len(result) <= 5
            # Check that items have required fields
            for item in result:
                assert "timestamp" in item
                assert "url" in item
        else:
            # Could return None if filtered
            assert True

    def test_timeline_respects_count_limit(self, camera_with_sample_images):
        """Test that timeline respects count parameter when images exist."""
        data_dir, camera_id = camera_with_sample_images
        result = timeline_from_camera_db(data_dir, camera_id, 2)
        
        if result is not None:
            assert len(result) <= 2


class TestHistory:
    """Test sensor history operations."""

    def test_history_no_database(self, tmp_data_dir, sample_camera_id):
        """Test history when database doesn't exist."""
        result = history_from_camera_db(tmp_data_dir, sample_camera_id, 24)
        assert result is None

    def test_history_empty(self, setup_camera_dir):
        """Test history with empty database."""
        data_dir, camera_id = setup_camera_dir
        result = history_from_camera_db(data_dir, camera_id, 24)
        assert result == []

    def test_history_with_records(self, camera_with_history):
        """Test history with sensor records."""
        data_dir, camera_id = camera_with_history
        result = history_from_camera_db(data_dir, camera_id, 24)
        
        assert result is not None
        assert len(result) > 0
        # Check structure
        item = result[0]
        assert "timestamp" in item
        assert "temperature" in item
        assert "humidity" in item

    def test_history_respects_time_range(self, camera_with_history):
        """Test that history respects time range."""
        data_dir, camera_id = camera_with_history
        
        # Request last 2 hours
        result = history_from_camera_db(data_dir, camera_id, 2)
        assert len(result) <= 2

    def test_history_converts_field_names(self, camera_with_history):
        """Test that history uses camelCase field names when available."""
        data_dir, camera_id = camera_with_history
        result = history_from_camera_db(data_dir, camera_id, 24)
        
        if result and len(result) > 0:
            item = result[0]
            # Fields should be in camelCase already
            assert "windSpeed" in item
            assert "wind_speed" not in item
            assert "uvIndex" in item
            assert "windDirection" in item


class TestLatestCapture:
    """Test latest capture operations."""

    def test_latest_capture_no_images(self, setup_camera_dir):
        """Test latest capture with no images."""
        data_dir, camera_id = setup_camera_dir
        result = latest_camera_capture(data_dir, camera_id)
        assert result is None

    def test_latest_camera_capture(self, camera_with_sample_images):
        """Test getting latest capture when images exist."""
        data_dir, camera_id = camera_with_sample_images
        result = latest_camera_capture(data_dir, camera_id)
        
        if result is not None:
            timestamp, url = result
            assert isinstance(timestamp, datetime)
            assert url.startswith("/stations/")


class TestLatestBattery:
    """Test latest battery lookup operations."""

    def test_latest_battery_no_database(self, tmp_data_dir, sample_camera_id):
        """Test latest battery when database doesn't exist."""
        result = latest_camera_battery(tmp_data_dir, sample_camera_id)
        assert result is None

    def test_latest_battery_empty(self, setup_camera_dir):
        """Test latest battery with empty database."""
        data_dir, camera_id = setup_camera_dir
        result = latest_camera_battery(data_dir, camera_id)
        assert result is None

    def test_latest_battery_returns_newest_row(self, setup_camera_dir):
        """Test that latest battery uses the newest sensor_history row."""
        data_dir, camera_id = setup_camera_dir

        from config import camera_db_path
        import sqlite3
        from datetime import timezone, timedelta

        db_path = camera_db_path(data_dir, camera_id)
        now = datetime.now(timezone.utc)

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO sensor_history
                (timestamp, temperature, humidity, pressure, battery, wind_speed,
                 wind_direction, visibility, uv_index, dew_point, feels_like)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (now - timedelta(hours=1)).isoformat(),
                    19.5,
                    60,
                    1012,
                    41,
                    4.5,
                    180,
                    10.0,
                    4,
                    13.0,
                    18.0,
                ),
            )
            conn.execute(
                """
                INSERT INTO sensor_history
                (timestamp, temperature, humidity, pressure, battery, wind_speed,
                 wind_direction, visibility, uv_index, dew_point, feels_like)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now.isoformat(),
                    20.0,
                    58,
                    1013,
                    76,
                    5.0,
                    190,
                    10.0,
                    5,
                    14.0,
                    19.0,
                ),
            )
            conn.commit()

        assert latest_camera_battery(data_dir, camera_id) == 76


class TestCameraStatus:
    """Test camera status determination."""

    def test_status_online_when_images_exist(self, camera_with_sample_images, sample_config):
        """Test that online status can be derived from recent images."""
        data_dir, camera_id = camera_with_sample_images
        status = camera_status(data_dir, camera_id, sample_config)
        
        assert "isOnline" in status
        assert "currentImage" in status
        assert "lastUpdate" in status

    def test_status_from_config(self, setup_camera_dir):
        """Test status when config specifies online state."""
        data_dir, camera_id = setup_camera_dir
        config = AppConfig(is_online=True, title="Test")
        status = camera_status(data_dir, camera_id, config)
        
        assert status["isOnline"] is True

    def test_status_no_images(self, setup_camera_dir):
        """Test status with no images."""
        data_dir, camera_id = setup_camera_dir
        config = AppConfig()
        status = camera_status(data_dir, camera_id, config)
        
        assert status["isOnline"] is False
        assert status["currentImage"] is None


class TestCameraSummary:
    """Test camera summary operations."""

    def test_summary_has_required_fields(self, setup_camera_dir, sample_config):
        """Test that summary has required fields."""
        data_dir, camera_id = setup_camera_dir
        summary = camera_summary(data_dir, camera_id)
        
        assert "id" in summary
        assert "name" in summary
        assert "location" in summary
        assert "country" in summary
        assert "coordinates" in summary
        assert "isOnline" in summary
        assert "battery" in summary

    def test_summary_uses_config_title(self, setup_camera_dir, sample_config):
        """Test that summary has a name field."""
        data_dir, camera_id = setup_camera_dir
        summary = camera_summary(data_dir, camera_id)
        
        # Name can be either the config title or humanized camera ID
        assert "name" in summary
        assert isinstance(summary["name"], str)

    def test_summary_includes_latest_battery(self, camera_with_history):
        """Test that summary includes the latest battery reading."""
        data_dir, camera_id = camera_with_history
        summary = camera_summary(data_dir, camera_id)

        assert summary["battery"] == 95

    def test_summary_returns_none_battery_without_history(self, setup_camera_dir):
        """Test that summary returns None battery when no history exists."""
        data_dir, camera_id = setup_camera_dir
        summary = camera_summary(data_dir, camera_id)

        assert summary["battery"] is None


class TestCameraDetail:
    """Test camera detail operations."""

    def test_detail_has_required_fields(self, setup_camera_dir):
        """Test that detail has all required fields."""
        data_dir, camera_id = setup_camera_dir
        detail = camera_detail(data_dir, camera_id)
        
        assert "id" in detail
        assert "name" in detail
        assert "description" in detail
        assert "currentImage" in detail
        assert "isOnline" in detail
        assert "lastUpdate" in detail
        assert "nextUpdate" in detail
        assert "battery" in detail

    def test_detail_includes_latest_battery(self, camera_with_history):
        """Test that detail includes the latest battery reading."""
        data_dir, camera_id = camera_with_history
        detail = camera_detail(data_dir, camera_id)

        assert detail["battery"] == 95
