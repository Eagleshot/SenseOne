from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from .mock_data import WEBCAM_SEED, generate_historical_data
except ImportError:
    from mock_data import WEBCAM_SEED, generate_historical_data


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from station_db import ensure_station_db  # noqa: E402  (needs BACKEND_DIR on sys.path)
from utils import iso_utc, parse_iso_timestamp, sanitize_station_id  # noqa: E402
DEFAULT_DATA_DIR = BACKEND_DIR / "data"
STATION_DB_FILENAME = "station.db"
STATION_CONFIG_FILENAME = "config.yaml"
STATION_META_FILENAME = "meta.json"
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
# Dev-only default password for seeded owner accounts (must satisfy the 12-char
# minimum enforced by users.create_user). Override with --owner-password.
DEFAULT_OWNER_PASSWORD = "devpassword123"


def _sanitize_station_id(raw_name: str) -> str:
    return sanitize_station_id(raw_name, default="station")


def _station_dir(data_dir: Path, station_id: str) -> Path:
    return data_dir / _sanitize_station_id(station_id)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _station_seed(station_id: str) -> dict[str, object]:
    normalized = _sanitize_station_id(station_id)
    for item in WEBCAM_SEED:
        if _sanitize_station_id(str(item.get("id") or "")) == normalized:
            return item
    return {}


def _station_config_yaml(station_id: str) -> str:
    seed = _station_seed(station_id)
    coordinates = seed.get("coordinates") or {}
    lines = [
        f"title: {_yaml_string(str(seed.get('name') or ''))}",
        f"description: {_yaml_string(str(seed.get('description') or ''))}",
        f"lat: {coordinates.get('lat', 0.0)}",
        f"lon: {coordinates.get('lng', 0.0)}",
        f"alt: {coordinates.get('altitude', 0.0)}",
        f"location: {_yaml_string(str(seed.get('location') or ''))}",
        f"country: {_yaml_string(str(seed.get('country') or ''))}",
        f"country_emoji: {_yaml_string(str(seed.get('countryEmoji') or ''))}",
        f"is_public: {str(bool(seed.get('is_public', True))).lower()}",
        f"station_start_time: {_yaml_string('06:00')}",
        f"station_stop_time: {_yaml_string('20:00')}",
        "use_sunrise_sunset: false",
        "capture_interval_minutes: 30",
    ]
    lines.append("")
    return "\n".join(lines)


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

    seed = _station_seed(station_id)
    seed_next_online = None
    if seed:
        seed_next_online = iso_utc(
            datetime.now(timezone.utc) + timedelta(minutes=int(seed.get("nextUpdateMinutesIn") or 0))
        )

    config_file = station_root / STATION_CONFIG_FILENAME
    if not config_file.exists() or overwrite:
        config_file.write_text(_station_config_yaml(station_id), encoding="utf-8")

    owner = seed.get("owner")
    meta_file = station_root / STATION_META_FILENAME
    if owner and (not meta_file.exists() or overwrite):
        meta_file.write_text(
            json.dumps({"owner": str(owner)}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    db_path = station_root / STATION_DB_FILENAME
    ensure_station_db(db_path)
    _ensure_seed_images(images_dir, overwrite)

    sensor_rows = [
        (
            row["timestamp"],
            json.dumps(
                {key: value for key, value in row.items() if key != "timestamp"},
                separators=(",", ":"),
            ),
        )
        for row in generate_historical_data(SENSOR_HISTORY_HOURS, station_id=station_id)
    ]
    with sqlite3.connect(db_path) as connection:
        if overwrite:
            connection.execute("DELETE FROM station_images")
            connection.execute("DELETE FROM sensor_history")
        else:
            latest_ts = connection.execute(
                "SELECT MAX(timestamp) FROM sensor_history"
            ).fetchone()[0]
            latest_at = parse_iso_timestamp(latest_ts)
            if latest_at is not None and latest_at >= (
                datetime.now(timezone.utc) - timedelta(hours=24)
            ):
                sensor_rows = []
            else:
                connection.execute("DELETE FROM sensor_history")

        if sensor_rows:
            connection.executemany(
                "INSERT INTO sensor_history (timestamp, metrics) VALUES (?, ?)",
                sensor_rows,
            )
            if seed_next_online:
                connection.execute(
                    "UPDATE sensor_history SET next_online = ? WHERE id = (SELECT MAX(id) FROM sensor_history)",
                    (seed_next_online,),
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


def _seed_owner_users(station_ids: list[str], password: str) -> None:
    """Create regular user accounts for every owner referenced by the seeded stations.

    Owners that already exist are left untouched, so re-running is safe and never
    clobbers a real password. Owners come from the WEBCAM_SEED ``owner`` field.
    """
    from users import create_user, get_user, init_users_db

    init_users_db()  # ensure the users table exists before inserting

    owners = sorted(
        {
            owner
            for station_id in station_ids
            if (owner := str(_station_seed(station_id).get("owner") or "").strip())
        }
    )
    for owner in owners:
        if get_user(owner) is not None:
            print(f"Owner account {owner!r} already exists; leaving it untouched.")
            continue
        try:
            create_user(owner, password)
            print(f"Created owner account {owner!r} (password: {password!r}).")
        except ValueError as exc:
            print(f"Failed to create owner account {owner!r}: {exc}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create sample per-station folders, config, and mock timeline DB rows."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory to create station folders under (default: ./data).",
    )
    parser.add_argument("--count", type=int, default=16, help="How many timeline images per station (default: 16).")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Clear existing station timeline rows and replace with mock data.",
    )
    parser.add_argument(
        "--station-id",
        action="append",
        default=[],
        help="Seed only specific station IDs (can be repeated). Defaults to all seeds.",
    )
    parser.add_argument(
        "--owner-password",
        default=DEFAULT_OWNER_PASSWORD,
        help=(
            "Password to assign to seeded owner accounts that don't exist yet "
            f"(default: {DEFAULT_OWNER_PASSWORD!r}). Existing accounts are left untouched."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    # users.db is resolved via config.get_data_dir(); point it at the same dir we
    # seed into so owner accounts land beside the station folders.
    import os

    os.environ["APP_DATA_DIR"] = str(data_dir)

    station_ids = args.station_id or [item["id"] for item in WEBCAM_SEED]
    if not station_ids:
        raise RuntimeError("No station IDs resolved from WEBCAM_SEED.")

    for station_id in station_ids:
        normalized = _sanitize_station_id(station_id)
        _seed_station(data_dir, normalized, args.count, args.overwrite)

    _seed_owner_users(station_ids, args.owner_password)

    print(f"Seeded {len(station_ids)} station folders into {data_dir}")


if __name__ == "__main__":
    main()
