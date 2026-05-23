"""Tests for configuration management."""

import pytest

from config import (
    read_station_config,
    write_station_config,
    ensure_station_dir,
)
from models import AppConfig


class TestConfigReadWrite:
    """Test reading and writing configuration."""

    def test_write_and_read_config(self, tmp_data_dir, sample_station_id, sample_config):
        """Test writing and reading back a config."""
        write_station_config(tmp_data_dir, sample_station_id, sample_config)
        read_config = read_station_config(tmp_data_dir, sample_station_id)
        
        assert read_config.title == sample_config.title
        assert read_config.description == sample_config.description
        assert read_config.lat == sample_config.lat
        assert read_config.lon == sample_config.lon

    def test_read_nonexistent_config(self, tmp_data_dir, sample_station_id):
        """Test reading config that doesn't exist creates default."""
        config = read_station_config(tmp_data_dir, sample_station_id)
        assert isinstance(config, AppConfig)
        assert config.title == ""  # Default values

    def test_config_file_created(self, tmp_data_dir, sample_station_id, sample_config):
        """Test that config file is created on write."""
        write_station_config(tmp_data_dir, sample_station_id, sample_config)
        config_path = tmp_data_dir / sample_station_id / "config.yaml"
        assert config_path.exists()

    def test_ensure_station_dir_creates_database(self, tmp_data_dir, sample_station_id):
        """Test that ensure_station_dir creates database."""
        ensure_station_dir(tmp_data_dir, sample_station_id)
        db_path = tmp_data_dir / sample_station_id / "station.db"
        assert db_path.exists()

    def test_ensure_station_dir_creates_images_dir(self, tmp_data_dir, sample_station_id):
        """Test that ensure_station_dir creates images directory."""
        ensure_station_dir(tmp_data_dir, sample_station_id)
        images_path = tmp_data_dir / sample_station_id / "images"
        assert images_path.exists()
        assert images_path.is_dir()


class TestConfigValidation:
    """Test configuration validation."""

    def test_config_time_validation(self):
        """Test that config validates time format."""
        with pytest.raises(ValueError, match="Time must be in HH:MM"):
            AppConfig(station_start_time="6:00")  # Invalid format

    def test_config_time_order_validation(self):
        """Test that start time must be before stop time."""
        with pytest.raises(ValueError, match="must be earlier than stop time"):
            AppConfig(station_start_time="20:00", station_stop_time="06:00")

    def test_config_capture_interval_bounds(self):
        """Test that capture interval is validated."""
        with pytest.raises(ValueError):
            AppConfig(capture_interval_minutes=0)  # Must be >= 1
        
        with pytest.raises(ValueError):
            AppConfig(capture_interval_minutes=1441)  # Must be <= 1440

    def test_config_description_length(self):
        """Test that description length is limited."""
        long_desc = "a" * 501
        with pytest.raises(ValueError):
            AppConfig(description=long_desc)


