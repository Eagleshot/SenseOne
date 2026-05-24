from __future__ import annotations

import math
import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any

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
        "owner": "alice",
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
        "owner": "bob",
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
        "owner": "alice",
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
    },
]

TIMEZONES = [
    {"value": "UTC", "label": "UTC"},
    {"value": "Europe/Zurich", "label": "Zurich (CET/CEST)"},
    {"value": "Europe/London", "label": "London (GMT/BST)"},
    {"value": "Europe/Paris", "label": "Paris (CET/CEST)"},
    {"value": "America/New_York", "label": "New York (EST/EDT)"},
    {"value": "America/Los_Angeles", "label": "Los Angeles (PST/PDT)"},
    {"value": "Asia/Tokyo", "label": "Tokyo (JST)"},
]

def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_historical_data(
    hours: int = 24, station_id: str | None = None
) -> list[dict[str, Any]]:
    station_id = station_id or "default"
    seed = int(hashlib.sha256(station_id.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    temp_offset = ((seed % 1000) - 500) / 50
    humidity_offset = ((seed // 7) % 20) - 10
    pressure_offset = ((seed // 13) % 10) - 5
    wind_direction_offset = (seed // 17) % 360
    visibility_offset = ((seed // 19) % 7) - 3
    battery_base = 40 + (seed // 23 % 41)
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
                "timestamp": _iso(timestamp),
                "temperature": round((base_temp + temp_variation) * 10) / 10,
                "humidity": round(
                    55
                    + 20 * math.sin(hour_of_day * math.pi / 12)
                    + humidity_offset
                    + (rng.random() - 0.5) * 10
                ),
                "pressure": round(1013 + pressure_offset + (rng.random() - 0.5) * 20),
                "battery": battery_level,
                "windSpeed": round((5 + rng.random() * 15) * 10) / 10,
                "windDirection": round((rng.random() * 360 + wind_direction_offset) % 360),
                "visibility": round((8 + rng.random() * 12 + visibility_offset) * 10) / 10,
                "uvIndex": round(rng.random() * 8) if 6 <= hour_of_day <= 18 else 0,
                "dewPoint": round((base_temp - 5 + (rng.random() - 0.5) * 3) * 10) / 10,
                "feelsLike": round((base_temp - 2 + (rng.random() - 0.5) * 2) * 10) / 10,
                "voltage": round(
                    (3.3 + 0.9 * battery_level / 100 + (rng.random() - 0.5) * 0.05) * 100
                ) / 100,
                "deviceTemperature": round((base_temp + 7 + (rng.random() - 0.5) * 4) * 10) / 10,
                "firmwareVersion": None,
                "nextStart": None,
                "cameraName": None,
                "wakeReason": "timer",
            }
        )
    return data
