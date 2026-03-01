from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

EXAMPLE_IMAGE_FILES = ["image0.png", "image1.png", "image2.png"]

WEBCAM_SEED = [
    {
        "id": "matterhorn-01",
        "name": "Matterhorn Peak",
        "location": "Zermatt, Switzerland",
        "coordinates": {"lat": 45.9763, "lng": 7.6586, "altitude": 3883},
        "imageFile": "image0.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 10,
        "nextUpdateMinutesIn": 20,
    },
    {
        "id": "eiger-north",
        "name": "Eiger Nordwand",
        "location": "Grindelwald, Switzerland",
        "coordinates": {"lat": 46.5775, "lng": 8.0053, "altitude": 3967},
        "imageFile": "image1.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 5,
        "nextUpdateMinutesIn": 25,
    },
    {
        "id": "mont-blanc",
        "name": "Mont Blanc Summit",
        "location": "Chamonix, France",
        "coordinates": {"lat": 45.8326, "lng": 6.8652, "altitude": 4808},
        "imageFile": "image2.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 15,
        "nextUpdateMinutesIn": 15,
    },
    {
        "id": "jungfrau-top",
        "name": "Jungfrau Top",
        "location": "Interlaken, Switzerland",
        "coordinates": {"lat": 46.5369, "lng": 7.9618, "altitude": 4158},
        "imageFile": "image0.png",
        "isOnline": False,
        "lastUpdateMinutesAgo": 120,
        "nextUpdateMinutesIn": 60,
    },
    {
        "id": "titlis-glacier",
        "name": "Titlis Glacier",
        "location": "Engelberg, Switzerland",
        "coordinates": {"lat": 46.7708, "lng": 8.4244, "altitude": 3238},
        "imageFile": "image1.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 8,
        "nextUpdateMinutesIn": 22,
    },
    {
        "id": "reykjavik-harbor",
        "name": "Reykjavik Harbor",
        "location": "Reykjavik, Iceland",
        "coordinates": {"lat": 64.1466, "lng": -21.9426, "altitude": 15},
        "imageFile": "image2.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 12,
        "nextUpdateMinutesIn": 18,
    },
    {
        "id": "yosemite-valley",
        "name": "Yosemite Valley",
        "location": "Yosemite, United States",
        "coordinates": {"lat": 37.7426, "lng": -119.5740, "altitude": 1219},
        "imageFile": "image0.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 7,
        "nextUpdateMinutesIn": 23,
    },
    {
        "id": "paris-seine",
        "name": "Seine River View",
        "location": "Paris, France",
        "coordinates": {"lat": 48.8584, "lng": 2.2945, "altitude": 35},
        "imageFile": "image1.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 9,
        "nextUpdateMinutesIn": 21,
    },
    {
        "id": "tokyo-skyline",
        "name": "Tokyo Skyline",
        "location": "Tokyo, Japan",
        "coordinates": {"lat": 35.6762, "lng": 139.6503, "altitude": 40},
        "imageFile": "image2.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 11,
        "nextUpdateMinutesIn": 19,
    },
    {
        "id": "bangkok-river",
        "name": "Chao Phraya River",
        "location": "Bangkok, Thailand",
        "coordinates": {"lat": 13.7563, "lng": 100.5018, "altitude": 5},
        "imageFile": "image0.png",
        "isOnline": True,
        "lastUpdateMinutesAgo": 6,
        "nextUpdateMinutesIn": 24,
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


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _image_url(file_name: str, base_url: str) -> str:
    _ = base_url
    return f"/example_images/{file_name}"


def get_webcams(base_url: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    webcams: list[dict[str, Any]] = []
    for item in WEBCAM_SEED:
        last_update = now - timedelta(minutes=item["lastUpdateMinutesAgo"])
        next_update = now + timedelta(minutes=item["nextUpdateMinutesIn"])
        image_url = _image_url(item["imageFile"], base_url)
        webcams.append(
            {
                "id": item["id"],
                "name": item["name"],
                "location": item["location"],
                "coordinates": item["coordinates"],
                "thumbnail": image_url,
                "currentImage": image_url,
                "isOnline": item["isOnline"],
                "lastUpdate": _iso(last_update),
                "nextUpdate": _iso(next_update),
            }
        )
    return webcams


def generate_historical_data(hours: int = 24) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for i in range(hours, -1, -1):
        timestamp = now - timedelta(hours=i)
        hour_of_day = timestamp.hour
        base_temp = 8 + 6 * math.sin((hour_of_day - 6) * math.pi / 12)
        temp_variation = (random.random() - 0.5) * 2
        data.append(
            {
                "timestamp": _iso(timestamp),
                "temperature": round((base_temp + temp_variation) * 10) / 10,
                "humidity": round(55 + 20 * math.sin(hour_of_day * math.pi / 12) + (random.random() - 0.5) * 10),
                "pressure": round(1013 + (random.random() - 0.5) * 20),
                "battery": max(20, round(100 - i * 0.8 + random.random() * 5)),
                "windSpeed": round((5 + random.random() * 15) * 10) / 10,
                "windDirection": round(random.random() * 360),
                "visibility": round((8 + random.random() * 12) * 10) / 10,
                "uvIndex": round(random.random() * 8) if 6 <= hour_of_day <= 18 else 0,
                "dewPoint": round((base_temp - 5 + (random.random() - 0.5) * 3) * 10) / 10,
                "feelsLike": round((base_temp - 2 + (random.random() - 0.5) * 2) * 10) / 10,
            }
        )
    return data


def generate_image_timestamps(base_url: str, count: int = 48) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for i in range(count, -1, -1):
        timestamp = now - timedelta(minutes=i * 30)
        images.append(
            {
                "timestamp": _iso(timestamp),
                "url": _image_url(EXAMPLE_IMAGE_FILES[i % len(EXAMPLE_IMAGE_FILES)], base_url),
            }
        )
    return images
