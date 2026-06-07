from __future__ import annotations

import base64
import hashlib
import math
import random
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from utils import iso_utc

WEBCAM_SEED = [
    {
        "id": "silvretta-glacier",
        "name": "Silvretta Glacier",
        "location": "Silvretta",
        "country": "Switzerland",
        "countryEmoji": "🇨🇭",
        "coordinates": {"lat": 46.8520, "lng": 10.1240, "altitude": 3360},
        "imageFile": "image0.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 10,
        "nextUpdateMinutesIn": 20,
        "is_public": True,
        "owner": "alice@example.com",
    },
    {
        "id": "gries-glacier",
        "name": "Gries Glacier",
        "location": "Gries",
        "country": "Switzerland",
        "countryEmoji": "🇨🇭",
        "coordinates": {"lat": 46.9000, "lng": 10.1500, "altitude": 2800},
        "imageFile": "image1.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 5,
        "nextUpdateMinutesIn": 25,
        "is_public": True,
        "owner": "bob@example.com",
    },
    {
        "id": "rhone-glacier",
        "name": "Rhone Glacier",
        "location": "Rhone",
        "country": "Switzerland",
        "countryEmoji": "🇨🇭",
        "coordinates": {"lat": 46.5170, "lng": 8.2846, "altitude": 2650},
        "imageFile": "image2.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 15,
        "nextUpdateMinutesIn": 15,
        "is_public": True,
        "owner": "alice@example.com",
    },
    {
        "id": "jungfrau-top",
        "name": "Jungfrau Top",
        "location": "Interlaken",
        "country": "Switzerland",
        "countryEmoji": "🇨🇭",
        "coordinates": {"lat": 46.5369, "lng": 7.9618, "altitude": 4158},
        "imageFile": "image0.png",
        "isOnline": False,
        "lastUpdateMinutesAgo": 120,
        "nextUpdateMinutesIn": 60,
        "is_public": True,
        "owner": "bob@example.com",
    },
    {
        "id": "titlis-glacier",
        "name": "Titlis Glacier",
        "location": "Engelberg",
        "country": "Switzerland",
        "countryEmoji": "🇨🇭",
        "coordinates": {"lat": 46.7708, "lng": 8.4244, "altitude": 3238},
        "imageFile": "image1.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 8,
        "nextUpdateMinutesIn": 22,
        "is_public": False,
        "owner": "alice@example.com",
    },
    {
        "id": "reykjavik-harbor",
        "name": "Reykjavik Harbor",
        "location": "Reykjavik",
        "country": "Iceland",
        "countryEmoji": "🇮🇸",
        "coordinates": {"lat": 64.1466, "lng": -21.9426, "altitude": 15},
        "imageFile": "image2.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 12,
        "nextUpdateMinutesIn": 18,
        "is_public": False,
        "owner": "bob@example.com",
    },
    {
        "id": "yosemite-valley",
        "name": "Yosemite Valley",
        "location": "Yosemite",
        "country": "United States",
        "countryEmoji": "🇺🇸",
        "coordinates": {"lat": 37.7426, "lng": -119.5740, "altitude": 1219},
        "imageFile": "image0.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 7,
        "nextUpdateMinutesIn": 23,
        "is_public": True,
        "owner": "bob@example.com",
    },
    {
        "id": "paris-seine",
        "name": "Seine River View",
        "description": "Monitoring the Seine through central Paris, this station captures changing river conditions, light, and weather around one of the city's most recognizable waterfront corridors.",
        "location": "Paris",
        "country": "France",
        "countryEmoji": "🇫🇷",
        "coordinates": {"lat": 48.8584, "lng": 2.2945, "altitude": 35},
        "imageFile": "image1.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 9,
        "nextUpdateMinutesIn": 21,
        "is_public": True,
        "owner": "alice@example.com",
    },
    {
        "id": "tokyo-skyline",
        "name": "Tokyo Skyline",
        "location": "Tokyo",
        "country": "Japan",
        "countryEmoji": "🇯🇵",
        "coordinates": {"lat": 35.6762, "lng": 139.6503, "altitude": 40},
        "imageFile": "image2.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 11,
        "nextUpdateMinutesIn": 19,
        "is_public": False,
        "owner": "alice@example.com",
    },
    {
        "id": "bangkok-river",
        "name": "Chao Phraya River",
        "location": "Bangkok",
        "country": "Thailand",
        "countryEmoji": "🇹🇭",
        "coordinates": {"lat": 13.7563, "lng": 100.5018, "altitude": 5},
        "imageFile": "image0.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 6,
        "nextUpdateMinutesIn": 24,
        "is_public": True,
        "owner": "bob@example.com",
    },
]

# Mock device housekeeping values, varied across stations/readings.
FIRMWARE_VERSIONS = ["1.0.3", "1.1.0", "1.2.0"]
WAKE_REASONS = ["timer", "timer", "timer", "boot", "motion"]


def generate_historical_data(
    hours: int = 24, station_id: str | None = None
) -> list[dict[str, Any]]:
    """Generate mock device-physical sensor readings.

    Only values a real sensor would measure are produced (temperature,
    humidity, pressure, battery, reception, voltage, device temperature).
    Weather-derived values (wind, visibility, UV, etc.) are intentionally
    absent — those come live from the weather proxy and are never stored.
    """
    station_id = station_id or "default"
    seed = int(hashlib.sha256(station_id.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    temp_offset = ((seed % 1000) - 500) / 50
    humidity_offset = ((seed // 7) % 20) - 10
    pressure_offset = ((seed // 13) % 10) - 5
    reception_base = 55 + (seed // 29 % 41)
    battery_base = 40 + (seed // 23 % 41)
    firmware_version = FIRMWARE_VERSIONS[seed % len(FIRMWARE_VERSIONS)]
    data: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for i in range(hours, -1, -1):
        timestamp = now - timedelta(hours=i)
        hour_of_day = timestamp.hour
        base_temp = 8 + 6 * math.sin((hour_of_day - 6) * math.pi / 12) + temp_offset / 5
        temp_variation = (rng.random() - 0.5) * 2
        battery_level = max(20, round(battery_base - i * 0.8 + rng.random() * 5))
        data.append(
            {
                "timestamp": iso_utc(timestamp),
                "temperature": round((base_temp + temp_variation) * 10) / 10,
                "humidity": round(
                    55
                    + 20 * math.sin(hour_of_day * math.pi / 12)
                    + humidity_offset
                    + (rng.random() - 0.5) * 10
                ),
                "pressure": round(1013 + pressure_offset + (rng.random() - 0.5) * 20),
                "battery": battery_level,
                "reception": max(0, min(100, round(reception_base + (rng.random() - 0.5) * 20))),
                "voltage": round(
                    (3.3 + 0.9 * battery_level / 100 + (rng.random() - 0.5) * 0.05) * 100
                ) / 100,
                "deviceTemperature": round((base_temp + 7 + (rng.random() - 0.5) * 4) * 10) / 10,
                "firmwareVersion": firmware_version,
                "wakeReason": rng.choice(WAKE_REASONS),
            }
        )
    return data


# ----- Seeding assets / config (shared by the seeder) ------------------------

# Dev-only default password for seeded owner accounts (>=12 chars, see
# users.create_user). Override with the seeder's --owner-password.
DEFAULT_OWNER_PASSWORD = "devpassword123"
SENSOR_HISTORY_HOURS = 168  # 7 days of hourly readings per station

SAMPLE_IMAGE_FILES = ["image0.png", "image1.png", "image2.png"]
SAMPLE_IMAGE_URLS = {
    "image0.png": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?fm=png&fit=crop&w=1024&h=576&q=80",
    "image1.png": "https://images.unsplash.com/photo-1483728642387-6c3bdd6c93e5?fm=png&fit=crop&w=1024&h=576&q=80",
    "image2.png": "https://images.unsplash.com/photo-1464823063530-08f10ed1a2dd?fm=png&fit=crop&w=1024&h=576&q=80",
}
# Tiny 1x1 PNG used when the sample images can't be downloaded (offline).
SAMPLE_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgOaI1xkAAAAASUVORK5CYII="
)


def _download_image(url: str, path: Path, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return True
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Eagleshot Mock Seeder)", "Accept": "image/*"},
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


def ensure_seed_images(images_dir: Path, overwrite: bool) -> None:
    """Make sure the sample source images exist (download, else embedded placeholder)."""
    for file_name in SAMPLE_IMAGE_FILES:
        source_file = images_dir / file_name
        if _download_image(SAMPLE_IMAGE_URLS[file_name], source_file, overwrite):
            continue
        if not source_file.exists():
            source_file.write_bytes(SAMPLE_PNG_BYTES)
