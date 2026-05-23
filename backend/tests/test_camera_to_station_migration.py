"""Tests for the one-time camera-to-station data migration."""

import sqlite3

import yaml

from migrations.rename_camera_to_station import migrate_data_dir


def _create_legacy_station(data_dir, station_id: str = "legacy-station"):
    station_dir = data_dir / station_id
    station_dir.mkdir(parents=True)
    (station_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Legacy Station",
                "camera_start_time": "07:00",
                "camera_stop_time": "19:00",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    db_path = station_dir / "camera.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE camera_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO camera_images (filename, content_type, size_bytes, created_at) VALUES (?, ?, ?, ?)",
            ("capture.jpg", "image/jpeg", 123, "2026-05-23T12:00:00Z"),
        )
        connection.commit()
    finally:
        connection.close()
    return station_dir


def test_camera_to_station_migration_updates_config_and_database(tmp_data_dir):
    station_dir = _create_legacy_station(tmp_data_dir)

    actions = migrate_data_dir(tmp_data_dir, dry_run=False)

    config = yaml.safe_load((station_dir / "config.yaml").read_text(encoding="utf-8"))
    assert config["station_start_time"] == "07:00"
    assert config["station_stop_time"] == "19:00"
    assert "camera_start_time" not in config
    assert "camera_stop_time" not in config
    assert not (station_dir / "camera.db").exists()
    assert (station_dir / "station.db").exists()
    with sqlite3.connect(station_dir / "station.db") as connection:
        row = connection.execute("SELECT filename, content_type, size_bytes FROM station_images").fetchone()
        assert row == ("capture.jpg", "image/jpeg", 123)
    assert any("updated" in action for action in actions)
    assert any("renamed" in action for action in actions)


def test_camera_to_station_migration_dry_run_does_not_write(tmp_data_dir):
    station_dir = _create_legacy_station(tmp_data_dir)

    actions = migrate_data_dir(tmp_data_dir, dry_run=True)

    config = yaml.safe_load((station_dir / "config.yaml").read_text(encoding="utf-8"))
    assert "camera_start_time" in config
    assert (station_dir / "camera.db").exists()
    assert not (station_dir / "station.db").exists()
    assert actions
