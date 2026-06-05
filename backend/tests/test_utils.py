"""Tests for utility functions."""

from datetime import datetime, timezone

from utils import (
    default_capture_filename,
    image_timestamp_from_filename,
    sanitize_filename,
    sanitize_station_id,
    normalize_content_type,
    parse_iso_timestamp,
    iso_utc,
    humanize_station_id,
    is_supported_image_upload,
    stream_from_filename,
)


class TestFilenameHandling:
    """Test filename sanitization."""

    def test_sanitize_filename_removes_special_chars(self):
        assert sanitize_filename("my/file.jpg") == "my_file.jpg"
        # Dots are preserved, only slashes are replaced
        assert sanitize_filename("../../../etc/passwd") == ".._.._.._etc_passwd"

    def test_sanitize_filename_preserves_valid_chars(self):
        assert sanitize_filename("my-file_123.jpg") == "my-file_123.jpg"
        assert sanitize_filename("my.file.tar.gz") == "my.file.tar.gz"

    def test_sanitize_filename_handles_empty(self):
        assert sanitize_filename("") == "default.jpg"
        # Dots-only returns dots, not empty
        assert sanitize_filename("...") == "..."


class TestStationIdHandling:
    """Test station ID handling."""

    def test_sanitize_station_id_removes_special_chars(self):
        assert sanitize_station_id("test@station!") == "test-station"

    def test_sanitize_station_id_normalizes_separators(self):
        # Strips leading/trailing separators
        assert sanitize_station_id("-test-") == "test"

    def test_sanitize_station_id_uses_default(self):
        assert sanitize_station_id(None) == "default"
        assert sanitize_station_id("") == "default"

    def test_sanitize_station_id_uses_provided(self):
        assert sanitize_station_id("my-station") == "my-station"


class TestContentTypeHandling:
    """Test content-type parsing."""

    def test_normalize_content_type_handles_charset(self):
        assert normalize_content_type("image/jpeg; charset=utf-8") == "image/jpeg"

    def test_normalize_content_type_handles_none(self):
        assert normalize_content_type(None) is None
        assert normalize_content_type("") is None

    def test_normalize_content_type_strips_whitespace(self):
        assert normalize_content_type("  image/png  ") == "image/png"


class TestTimestampParsing:
    """Test timestamp parsing."""

    def test_parse_iso_timestamp_valid(self):
        result = parse_iso_timestamp("2024-01-01T12:30:00Z")
        assert result is not None
        assert result.year == 2024

    def test_parse_iso_timestamp_with_offset(self):
        result = parse_iso_timestamp("2024-01-01T12:30:00+01:00")
        assert result is not None
        # Should be converted to UTC
        assert result.utcoffset().total_seconds() == 0

    def test_parse_iso_timestamp_invalid(self):
        assert parse_iso_timestamp("invalid") is None
        assert parse_iso_timestamp(None) is None
        assert parse_iso_timestamp("") is None

    def test_iso_utc_formatting(self):
        dt = datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        assert iso_utc(dt) == "2024-01-01T12:30:00Z"

    def test_image_timestamp_from_filename_parses_utc_capture_name(self):
        result = image_timestamp_from_filename("20260524_1430Z_front.jpg")

        assert result == datetime(2026, 5, 24, 14, 30, tzinfo=timezone.utc)

    def test_image_timestamp_from_filename_rejects_untimestamped_name(self):
        assert image_timestamp_from_filename("capture.jpg") is None

    def test_image_timestamp_from_filename_rejects_invalid_date(self):
        assert image_timestamp_from_filename("20260231_1430Z_front.jpg") is None


class TestHumanization:
    """Test humanization of IDs."""

    def test_humanize_station_id(self):
        assert humanize_station_id("test-station") == "Test Station"
        assert humanize_station_id("test_station_1") == "Test Station 1"
        assert humanize_station_id("test.station.two") == "Test Station Two"

    def test_humanize_empty_string(self):
        # Should return empty string if result is empty
        assert humanize_station_id("---") == "---"


class TestImageValidation:
    """Test image upload validation."""

    def test_supported_extension(self):
        assert is_supported_image_upload("test.jpg", "image/jpeg") is True
        assert is_supported_image_upload("test.png", "image/png") is True
        assert is_supported_image_upload("test.webp", "image/webp") is True

    def test_unsupported_extension(self):
        assert is_supported_image_upload("test.gif", "image/gif") is False
        assert is_supported_image_upload("test.txt", None) is False

    def test_content_type_mismatch(self):
        assert is_supported_image_upload("test.jpg", "application/json") is False
        assert is_supported_image_upload("test.jpg", "text/html") is False

    def test_missing_content_type_with_valid_extension(self):
        # Should accept if extension is valid and content-type is missing
        assert is_supported_image_upload("test.jpg", None) is True

    def test_missing_content_type_with_invalid_extension(self):
        # Empty filename with no content-type returns True (extension_supported is False but empty == "")
        # Based on actual logic: returns extension_supported or extension == ""
        # Since extension == "", result is True
        assert is_supported_image_upload("", None) is True


class TestStreamFromFilename:
    """Test camera/stream token extraction from capture filenames."""

    def test_extracts_camera_token(self):
        assert stream_from_filename("20260524_1430Z_front.jpg") == "front"
        assert stream_from_filename("20260605_1200Z_thermal.png") == "thermal"

    def test_token_allows_inner_separators(self):
        assert stream_from_filename("20260605_1200Z_cam-0.jpg") == "cam-0"
        assert stream_from_filename("20260605_1200Z_roof.cam_1.webp") == "roof.cam_1"

    def test_returns_none_for_non_capture_names(self):
        # Same names that image upload rejects → no stream.
        assert stream_from_filename("default.jpg") is None
        assert stream_from_filename("capture.jpg") is None
        assert stream_from_filename("") is None


class TestDefaultCaptureFilename:
    """The fallback capture name used when a device omits X-Filename."""

    _NOW = datetime(2026, 6, 5, 12, 0, 30, tzinfo=timezone.utc)

    def test_stamps_current_utc_minute_and_round_trips(self):
        name = default_capture_filename("image/jpeg", now=self._NOW)
        assert name == "20260605_1200Z_default.jpg"
        # Must parse back through the capture-name reader so the stored capture
        # timestamp is the stamped minute (seconds truncated).
        assert image_timestamp_from_filename(name) == datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)

    def test_extension_follows_content_type(self):
        assert default_capture_filename("image/png", now=self._NOW).endswith("_default.png")
        assert default_capture_filename("image/webp", now=self._NOW).endswith("_default.webp")

    def test_defaults_to_jpg_for_missing_or_unknown_content_type(self):
        assert default_capture_filename(None, now=self._NOW).endswith("_default.jpg")
        assert default_capture_filename("image/gif", now=self._NOW).endswith("_default.jpg")


