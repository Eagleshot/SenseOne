"""Tests for station upload storage (blob on disk + database metadata row)."""

import pytest
from fastapi import HTTPException

from routes.device_ingestion import store_uploaded_image
from tests import _db

# Minimal bytes that pass content sniffing as a real JPEG (SOI + APP0/JFIF).
_JPEG_BYTES = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"


def test_store_uploaded_image_persists_file_and_db_row(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir

    stored_filename, image_url = store_uploaded_image(
        station_id=station_id,
        filename="20260524_1430Z_front.jpg",
        body=_JPEG_BYTES,
        content_type="image/jpeg",
    )

    assert stored_filename == "20260524_1430Z_front.jpg"
    assert image_url == f"/stations/{station_id}/images/{stored_filename}"

    image_path = data_dir / station_id / "images" / stored_filename
    assert image_path.read_bytes() == _JPEG_BYTES

    row = _db.latest_image(station_id)
    assert row["filename"] == stored_filename
    assert row["content_type"] == "image/jpeg"
    assert row["size_bytes"] == len(_JPEG_BYTES)
    assert row["captured_at"] == "2026-05-24T14:30:00Z"


def test_store_uploaded_image_uses_timestamped_filename_as_capture_time(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir

    stored_filename, _image_url = store_uploaded_image(
        station_id=station_id,
        filename="20260524_1430Z_front.jpg",
        body=_JPEG_BYTES,
        content_type="image/jpeg",
    )

    assert stored_filename == "20260524_1430Z_front.jpg"
    assert _db.latest_image(station_id)["captured_at"] == "2026-05-24T14:30:00Z"


def test_store_uploaded_image_rejects_non_image_bytes(setup_station_dir, monkeypatch):
    _, station_id = setup_station_dir

    with pytest.raises(HTTPException) as exc_info:
        store_uploaded_image(
            station_id=station_id,
            filename="20260524_1430Z_front.jpg",
            body=b"<html>not an image</html>",
            content_type="image/jpeg",
        )

    assert exc_info.value.status_code == 415


def test_store_uploaded_image_rejects_malformed_capture_filename(setup_station_dir, monkeypatch):
    _, station_id = setup_station_dir

    with pytest.raises(HTTPException) as exc_info:
        store_uploaded_image(
            station_id=station_id,
            filename="capture.jpg",
            body=b"fake-jpeg-bytes",
            content_type="image/jpeg",
        )

    assert exc_info.value.status_code == 422
