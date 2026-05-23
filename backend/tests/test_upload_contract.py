"""Tests for station upload storage."""

import sqlite3

from config import station_db_path
from routes.device_ingestion import store_uploaded_image


def test_store_uploaded_image_persists_file_and_db_row(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))

    stored_filename, image_url = store_uploaded_image(
        station_id=station_id,
        filename="capture.jpg",
        body=b"fake-jpeg-bytes",
        content_type="image/jpeg",
    )

    assert stored_filename.endswith("-capture.jpg")
    assert image_url == f"/stations/{station_id}/images/{stored_filename}"

    image_path = data_dir / station_id / "images" / stored_filename
    assert image_path.read_bytes() == b"fake-jpeg-bytes"

    with sqlite3.connect(station_db_path(data_dir, station_id)) as connection:
        row = connection.execute(
            "SELECT filename, content_type, size_bytes FROM station_images ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row == (stored_filename, "image/jpeg", len(b"fake-jpeg-bytes"))


