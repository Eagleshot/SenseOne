"""Tests for configuration management."""

import pytest

from config import (
    read_camera_config,
    write_camera_config,
    ensure_camera_dir,
    camera_config_yaml_for_values,
    default_camera_config,
)
from models import AppConfig


class TestConfigReadWrite:
    """Test reading and writing configuration."""

    def test_write_and_read_config(self, tmp_data_dir, sample_camera_id, sample_config):
        """Test writing and reading back a config."""
        write_camera_config(tmp_data_dir, sample_camera_id, sample_config)
        read_config = read_camera_config(tmp_data_dir, sample_camera_id)
        
        assert read_config.title == sample_config.title
        assert read_config.description == sample_config.description
        assert read_config.lat == sample_config.lat
        assert read_config.lon == sample_config.lon

    def test_read_nonexistent_config(self, tmp_data_dir, sample_camera_id):
        """Test reading config that doesn't exist creates default."""
        config = read_camera_config(tmp_data_dir, sample_camera_id)
        assert isinstance(config, AppConfig)
        assert config.title == ""  # Default values

    def test_config_file_created(self, tmp_data_dir, sample_camera_id, sample_config):
        """Test that config file is created on write."""
        write_camera_config(tmp_data_dir, sample_camera_id, sample_config)
        config_path = tmp_data_dir / sample_camera_id / "config.yaml"
        assert config_path.exists()

    def test_ensure_camera_dir_creates_database(self, tmp_data_dir, sample_camera_id):
        """Test that ensure_camera_dir creates database."""
        ensure_camera_dir(tmp_data_dir, sample_camera_id)
        db_path = tmp_data_dir / sample_camera_id / "camera.db"
        assert db_path.exists()

    def test_ensure_camera_dir_creates_images_dir(self, tmp_data_dir, sample_camera_id):
        """Test that ensure_camera_dir creates images directory."""
        ensure_camera_dir(tmp_data_dir, sample_camera_id)
        images_path = tmp_data_dir / sample_camera_id / "images"
        assert images_path.exists()
        assert images_path.is_dir()


class TestConfigValidation:
    """Test configuration validation."""

    def test_config_time_validation(self):
        """Test that config validates time format."""
        with pytest.raises(ValueError, match="Time must be in HH:MM"):
            AppConfig(camera_start_time="6:00")  # Invalid format

    def test_config_time_order_validation(self):
        """Test that start time must be before stop time."""
        with pytest.raises(ValueError, match="must be earlier than stop time"):
            AppConfig(camera_start_time="20:00", camera_stop_time="06:00")

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


class TestConfigYAML:
    """Test YAML generation."""

    def test_config_yaml_generated(self, sample_config):
        """Test that YAML can be generated from config."""
        from config import camera_config_yaml_for_values
        yaml = camera_config_yaml_for_values(sample_config)
        assert isinstance(yaml, str)
        assert "title" in yaml
        assert "camera_start_time" in yaml

    def test_camera_config_yaml_default(self, sample_camera_id):
        """Test default config YAML generation."""
        yaml_str = camera_config_yaml_for_values(default_camera_config(sample_camera_id))
        assert isinstance(yaml_str, str)
        assert "camera_start_time" in yaml_str
        assert "camera_stop_time" in yaml_str
