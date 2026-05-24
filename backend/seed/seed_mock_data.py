from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

try:
    from .mock_data import WEBCAM_SEED, generate_historical_data
except ImportError:
    from mock_data import WEBCAM_SEED, generate_historical_data


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BACKEND_DIR / "data"
STATION_DB_FILENAME = "station.db"
STATION_CONFIG_FILENAME = "config.yaml"
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


def _sanitize_station_id(raw_name: str) -> str:
    if not raw_name:
        return "station"
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", raw_name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "station"


def _station_dir(data_dir: Path, station_id: str) -> Path:
    return data_dir / _sanitize_station_id(station_id)


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


def _station_seed(station_id: str) -> dict[str, object]:
    normalized = _sanitize_station_id(station_id)
    for item in WEBCAM_SEED:
        if _sanitize_station_id(str(item.get("id") or "")) == normalized:
            return item
    return {}


def _station_config_yaml(station_id: str) -> str:
    seed = _station_seed(station_id)
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
            f"last_online: {_yaml_optional_string(_iso_utc(last_online) if last_online else None)}",
            f"next_online: {_yaml_optional_string(_iso_utc(next_online) if next_online else None)}",
            f"station_start_time: {_yaml_string('06:00')}",
            f"station_stop_time: {_yaml_string('20:00')}",
            "use_sunrise_sunset: false",
            "capture_interval_minutes: 30",
            "",
        ]
    )


def _ensure_station_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS station_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_images_created_at ON station_images(created_at)"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(station_images)")}
        if "next_online" not in columns:
            connection.execute("ALTER TABLE station_images ADD COLUMN next_online TEXT")
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
            "CREATE INDEX IF NOT EXISTS idx_sensor_history_timestamp ON sensor_history(timestamp)"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(sensor_history)")}
        if "next_online" not in columns:
            connection.execute("ALTER TABLE sensor_history ADD COLUMN next_online TEXT")
        connection.commit()


def _latest_runtime_status(db_path: Path) -> tuple[str | None, str | None, str | None, int | None]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        image = connection.execute(
            "SELECT id, created_at, next_online FROM station_images ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        sensor = connection.execute(
            "SELECT id, timestamp, next_online FROM sensor_history ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()

    candidates = []
    if image:
        candidates.append(("station_images", image["id"], image["created_at"], image["next_online"]))
    if sensor:
        candidates.append(("sensor_history", sensor["id"], sensor["timestamp"], sensor["next_online"]))

    parsed = []
    for table, row_id, timestamp, next_online in candidates:
        parsed_at = _parse_iso_utc(timestamp)
        if parsed_at is not None:
            parsed.append((parsed_at, table, row_id, next_online))
    if not parsed:
        return None, None, None, None

    latest_at, table, row_id, next_online = max(parsed, key=lambda item: item[0])
    return _iso_utc(latest_at), next_online, table, row_id


def _sync_runtime_status(data_dir: Path, station_id: str, seed_next_online: str | None) -> None:
    station_root = _station_dir(data_dir, station_id)
    db_path = station_root / STATION_DB_FILENAME
    config_file = station_root / STATION_CONFIG_FILENAME

    last_online, next_online, table, row_id = _latest_runtime_status(db_path)
    parsed_next = _parse_iso_utc(seed_next_online)
    parsed_last = _parse_iso_utc(last_online)
    if row_id is not None and next_online is None and parsed_next and parsed_last and parsed_next > parsed_last:
        next_online = _iso_utc(parsed_next)
        with sqlite3.connect(db_path) as connection:
            connection.execute(f"UPDATE {table} SET next_online = ? WHERE id = ?", (next_online, row_id))
            connection.commit()

    last_online, next_online, _table, _row_id = _latest_runtime_status(db_path)
    document = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    document["last_online"] = last_online
    document["next_online"] = next_online
    config_file.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")


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


def _seed_station(data_dir: Path, station_id: str, count: int, overwrite: bool) -> None:
    station_root = _station_dir(data_dir, station_id)
    images_dir = station_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    config_file = station_root / STATION_CONFIG_FILENAME
    if not config_file.exists() or overwrite:
        config_file.write_text(_station_config_yaml(station_id), encoding="utf-8")

    db_path = station_root / STATION_DB_FILENAME
    _ensure_station_schema(db_path)
    _ensure_seed_images(images_dir, overwrite)

    if overwrite:
        with sqlite3.connect(db_path) as connection:
            connection.execute("DELETE FROM station_images")
            connection.execute("DELETE FROM sensor_history")
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
        for row in generate_historical_data(SENSOR_HISTORY_HOURS, station_id=station_id)
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

    if count > 0:
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
                INSERT INTO station_images (filename, content_type, size_bytes, created_at, next_online)
                VALUES (?, ?, ?, ?, NULL)
                """,
                rows,
            )
            connection.commit()

    seed = _station_seed(station_id)
    seed_next_online = None
    if seed:
        seed_next_online = _iso_utc(
            datetime.now(timezone.utc) + timedelta(minutes=int(seed.get("nextUpdateMinutesIn") or 0))
        )
    _sync_runtime_status(data_dir, station_id, seed_next_online)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create sample per-station folders, config, and mock timeline DB rows.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory to create station folders under (default: ./data).",
    )
    parser.add_argument("--count", type=int, default=16, help="How many timeline images per station (default: 16).")
    parser.add_argument("--overwrite", action="store_true", help="Clear existing station timeline rows and replace with mock data.")
    parser.add_argument(
        "--station-id",
        action="append",
        default=[],
        help="Seed only specific station IDs (can be repeated). Defaults to all seeds.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    station_ids = args.station_id or [item["id"] for item in WEBCAM_SEED]
    if not station_ids:
        raise RuntimeError("No station IDs resolved from WEBCAM_SEED.")

    for station_id in station_ids:
        normalized = _sanitize_station_id(station_id)
        _seed_station(data_dir, normalized, args.count, args.overwrite)

    print(f"Seeded {len(station_ids)} station folders into {data_dir}")


if __name__ == "__main__":
    main()
