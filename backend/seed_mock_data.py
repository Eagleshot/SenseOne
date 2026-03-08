from __future__ import annotations

import argparse
import base64
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from .mock_data import WEBCAM_SEED
except ImportError:
    from mock_data import WEBCAM_SEED


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


def _sanitize_camera_id(raw_name: str) -> str:
    if not raw_name:
        return "camera"
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", raw_name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "camera"


def _camera_dir(data_dir: Path, camera_id: str) -> Path:
    return data_dir / _sanitize_camera_id(camera_id)


def _camera_config_yaml(camera_id: str) -> str:
    return "\n".join(
        [
            f"camera_id: {camera_id}",
            "camera_start_time: \"06:00\"",
            "camera_stop_time: \"20:00\"",
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
