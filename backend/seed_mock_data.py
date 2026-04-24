from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from .mock_data import CHART_DATA_SOURCE_SEED, WEBCAM_SEED, generate_historical_data
except ImportError:
    from mock_data import CHART_DATA_SOURCE_SEED, WEBCAM_SEED, generate_historical_data


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
CAMERA_DB_FILENAME = "camera.db"
CAMERA_CONFIG_FILENAME = "config.yaml"
SAMPLE_IMAGE_FILES = ["image0.png", "image1.png", "image2.png"]
SAMPLE_IMAGE_URLS = {
    "image0.png": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?fm=png&fit=crop&w=1024&h=576&q=80",
    "image1.png": "https://images.unsplash.com/photo-1483728642387-6c3bdd6c93e5?fm=png&fit=crop&w=1024&h=576&q=80",
    "image2.png": "https://images.unsplash.com/photo-1464823063530-08f10ed1a2dd?fm=png&fit=crop&w=1024&h=576&q=80",
}
SAMPLE_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgOaI1xkAAAAASUVORK5CYII="
)
SENSOR_HISTORY_HOURS = 168


def _sanitize_camera_id(raw_name: str) -> str:
    if not raw_name:
        return "camera"
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", raw_name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "camera"


def _camera_dir(data_dir: Path, camera_id: str) -> Path:
    return data_dir / _sanitize_camera_id(camera_id)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_optional_string(value: str | None) -> str:
    if value is None:
        return "null"
    return _yaml_string(value)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _camera_seed(camera_id: str) -> dict[str, object]:
    normalized = _sanitize_camera_id(camera_id)
    for item in WEBCAM_SEED:
        if _sanitize_camera_id(str(item.get("id") or "")) == normalized:
            return item
    return {}


def _camera_config_yaml(camera_id: str) -> str:
    seed = _camera_seed(camera_id)
    coordinates = seed.get("coordinates") or {}
    now = datetime.now(timezone.utc)
    last_online = None
    next_online = None
    if seed:
        last_online = now - timedelta(minutes=int(seed.get("lastUpdateMinutesAgo") or 0))
        next_online = now + timedelta(minutes=int(seed.get("nextUpdateMinutesIn") or 0))
    return "\n".join(
        [
            f"title: {_yaml_string(str(seed.get('name') or ''))}",
            f"description: {_yaml_string(str(seed.get('description') or ''))}",
            f"lat: {coordinates.get('lat', 0.0)}",
            f"lon: {coordinates.get('lng', 0.0)}",
            f"alt: {coordinates.get('altitude', 0.0)}",
            f"location: {_yaml_string(str(seed.get('location') or ''))}",
            f"country: {_yaml_string(str(seed.get('country') or ''))}",
            f"country_emoji: {_yaml_string(str(seed.get('countryEmoji') or ''))}",
            f"is_online: {'true' if seed.get('isOnline') is True else 'false' if seed.get('isOnline') is False else 'null'}",
            f"last_online: {_yaml_optional_string(_iso_utc(last_online) if last_online else None)}",
            f"next_online: {_yaml_optional_string(_iso_utc(next_online) if next_online else None)}",
            f"camera_start_time: {_yaml_string('06:00')}",
            f"camera_stop_time: {_yaml_string('20:00')}",
            "use_sunrise_sunset: false",
            "capture_interval_minutes: 30",
            "",
        ]
    )


def _ensure_camera_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS camera_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL NOT NULL,
                humidity INTEGER NOT NULL,
                pressure INTEGER NOT NULL,
                battery INTEGER NOT NULL,
                wind_speed REAL NOT NULL,
                wind_direction INTEGER NOT NULL,
                visibility REAL NOT NULL,
                uv_index INTEGER NOT NULL,
                dew_point REAL NOT NULL,
                feels_like REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chart_data_sources (
                source_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                icon_key TEXT NOT NULL,
                color_value TEXT NOT NULL
            )
            """
        )
        chart_source_columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info(chart_data_sources)").fetchall()
        ]
        expected_chart_source_columns = [
            "source_id",
            "label",
            "icon_key",
            "color_value",
        ]
        if chart_source_columns and chart_source_columns != expected_chart_source_columns:
            connection.execute("ALTER TABLE chart_data_sources RENAME TO chart_data_sources_legacy")
            connection.execute(
                """
                CREATE TABLE chart_data_sources (
                    source_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    icon_key TEXT NOT NULL,
                    color_value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO chart_data_sources (
                    source_id,
                    label,
                    icon_key,
                    color_value
                )
                SELECT
                    source_id,
                    label,
                    icon_key,
                    color_value
                FROM chart_data_sources_legacy
                """
            )
            connection.execute("DROP TABLE chart_data_sources_legacy")
        connection.commit()


def _download_image(url: str, path: Path, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return True

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Eagleshot Mock Seeder)",
                "Accept": "image/*",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"Status {response.status} from {url}")
            payload = response.read()
            if not payload:
                raise RuntimeError(f"Empty image payload from {url}")
            path.write_bytes(payload)
            return True
    except (OSError, urllib.error.URLError, RuntimeError) as exc:
        print(f"Failed to download mock image from {url}: {exc}")
        return False


def _ensure_seed_images(images_dir: Path, overwrite: bool) -> None:
    for file_name in SAMPLE_IMAGE_FILES:
        source_file = images_dir / file_name
        if _download_image(SAMPLE_IMAGE_URLS[file_name], source_file, overwrite):
            continue
        if not source_file.exists():
            source_file.write_bytes(SAMPLE_PNG_BYTES)


def _seed_camera(data_dir: Path, camera_id: str, count: int, overwrite: bool) -> None:
    camera_root = _camera_dir(data_dir, camera_id)
    images_dir = camera_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    config_file = camera_root / CAMERA_CONFIG_FILENAME
    if not config_file.exists() or overwrite:
        config_file.write_text(_camera_config_yaml(camera_id), encoding="utf-8")

    db_path = camera_root / CAMERA_DB_FILENAME
    _ensure_camera_schema(db_path)
    _ensure_seed_images(images_dir, overwrite)

    if overwrite:
        with sqlite3.connect(db_path) as connection:
            connection.execute("DELETE FROM camera_images")
            connection.execute("DELETE FROM sensor_history")
            connection.execute("DELETE FROM chart_data_sources")
            connection.commit()

    with sqlite3.connect(db_path) as connection:
        if overwrite:
            connection.execute("DELETE FROM chart_data_sources")

        source_rows = [
            (
                source["id"],
                source["label"],
                source["icon"],
                source["color"],
            )
            for source in CHART_DATA_SOURCE_SEED
        ]
        if source_rows:
            connection.executemany(
                """
                INSERT OR REPLACE INTO chart_data_sources (
                    source_id,
                    label,
                    icon_key,
                    color_value
                )
                VALUES (?, ?, ?, ?)
                """,
                source_rows,
            )
            connection.commit()

    sensor_rows = [
        (
            row["timestamp"],
            row["temperature"],
            row["humidity"],
            row["pressure"],
            row["battery"],
            row["windSpeed"],
            row["windDirection"],
            row["visibility"],
            row["uvIndex"],
            row["dewPoint"],
            row["feelsLike"],
        )
        for row in generate_historical_data(SENSOR_HISTORY_HOURS, webcam_id=camera_id)
    ]
    with sqlite3.connect(db_path) as connection:
        refresh_history = overwrite
        if overwrite:
            connection.execute("DELETE FROM sensor_history")
        else:
            latest_history_timestamp = connection.execute(
                "SELECT MAX(timestamp) FROM sensor_history"
            ).fetchone()[0]
            latest_history_at = _parse_iso_utc(latest_history_timestamp)
            refresh_history = latest_history_at is None or latest_history_at < (datetime.now(timezone.utc) - timedelta(hours=24))
            if refresh_history:
                connection.execute("DELETE FROM sensor_history")
            else:
                sensor_rows = []

        if sensor_rows:
            connection.executemany(
                """
                INSERT INTO sensor_history (
                    timestamp,
                    temperature,
                    humidity,
                    pressure,
                    battery,
                    wind_speed,
                    wind_direction,
                    visibility,
                    uv_index,
                    dew_point,
                    feels_like
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                sensor_rows,
            )
            connection.commit()

    if count <= 0:
        return

    now = datetime.now(timezone.utc)
    rows = []
    with sqlite3.connect(db_path) as connection:
        for index in range(count):
            timestamp = now - timedelta(minutes=(count - index) * 30)
            source_name = SAMPLE_IMAGE_FILES[index % len(SAMPLE_IMAGE_FILES)]
            filename = f"{int(timestamp.timestamp() * 1000)}-{source_name}"
            destination = images_dir / filename
            if not destination.exists() or overwrite:
                source_file = images_dir / source_name
                if source_file.exists():
                    destination.write_bytes(source_file.read_bytes())
                else:
                    destination.write_bytes(SAMPLE_PNG_BYTES)
            size_bytes = destination.stat().st_size
            rows.append((filename, "image/png", size_bytes, timestamp.isoformat().replace("+00:00", "Z")))

        connection.executemany(
            """
            INSERT INTO camera_images (filename, content_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create sample per-camera folders, config, and mock timeline DB rows.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory to create camera folders under (default: ./data).",
    )
    parser.add_argument("--count", type=int, default=16, help="How many timeline images per camera (default: 16).")
    parser.add_argument("--overwrite", action="store_true", help="Clear existing camera timeline rows and replace with mock data.")
    parser.add_argument(
        "--camera-id",
        action="append",
        default=[],
        help="Seed only specific camera IDs (can be repeated). Defaults to all seeds.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    camera_ids = args.camera_id or [item["id"] for item in WEBCAM_SEED]
    if not camera_ids:
        raise RuntimeError("No camera IDs resolved from WEBCAM_SEED.")

    for camera_id in camera_ids:
        normalized = _sanitize_camera_id(camera_id)
        _seed_camera(data_dir, normalized, args.count, args.overwrite)

    print(f"Seeded {len(camera_ids)} camera folders into {data_dir}")


if __name__ == "__main__":
    main()
