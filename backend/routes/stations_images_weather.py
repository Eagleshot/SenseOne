"""Weather and image serving routes."""

import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth import get_optional_current_user
from config import read_camera_config, get_data_dir
from station_access import require_station_view
from utils import media_type_from_path, sanitize_filename
from routes import ValidStationId


router = APIRouter(tags=["Stations"])


@router.get(
    "/stations/{station_id}/images/{filename}",
    summary="Get station image",
    description=(
        "Serve a single image file from the station's image directory. "
        "`filename` must be the value returned by an image-captures listing — "
        "anything outside the station directory or with path-traversal characters "
        "is rejected with 400."
    ),
)
def get_station_image(
    station_id: ValidStationId,
    filename: str,
    user=Depends(get_optional_current_user),
) -> FileResponse:
    if filename != sanitize_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    require_station_view(station_id, user)
    data_dir = get_data_dir()
    image_path = data_dir / station_id / "images" / filename
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(image_path, media_type=media_type_from_path(image_path))


async def fetch_openweather(endpoint: str, lat: float, lon: float, units: str = "metric") -> dict:
    """Fetch data from OpenWeather API.

    Upstream non-2xx responses are surfaced as 502 (bad gateway) so the client
    cannot mistake them for problems with this service. The underlying status
    is logged for diagnostics.
    """
    import logging

    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OPENWEATHER_API_KEY.")

    url = f"https://api.openweathermap.org/data/2.5/{endpoint}"
    params = {"lat": lat, "lon": lon, "units": units, "appid": api_key}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
    except httpx.RequestError as exc:
        logging.warning("OpenWeather request error: %s", exc)
        raise HTTPException(status_code=502, detail="OpenWeather request failed.") from exc

    if response.status_code >= 400:
        logging.warning(
            "OpenWeather upstream returned %s for %s",
            response.status_code,
            endpoint,
        )
        raise HTTPException(status_code=502, detail="OpenWeather request failed.")
    return response.json()


def camera_coordinates_for_weather(base_dir: Path, camera_id: str) -> tuple[float, float]:
    """Get coordinates for weather API calls."""
    config = read_camera_config(base_dir, camera_id)
    lat = config.lat
    lon = config.lon
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Camera coordinates are invalid.")
    if lat == 0 and lon == 0:
        raise HTTPException(status_code=400, detail="Camera coordinates are not configured.")
    return lat, lon


@router.get(
    "/stations/{station_id}/weather/current",
    summary="Get current weather",
    description=(
        "Proxy the current weather for this station from OpenWeather, using the "
        "station's stored coordinates and metric units. Upstream failures are "
        "surfaced as 502 so clients don't mistake them for issues with this "
        "service. Requires `OPENWEATHER_API_KEY` in the server environment."
    ),
)
async def get_station_current_weather(
    station_id: ValidStationId,
    user=Depends(get_optional_current_user),
) -> dict:
    require_station_view(station_id, user)
    lat, lon = camera_coordinates_for_weather(get_data_dir(), station_id)
    return await fetch_openweather("weather", lat, lon, "metric")


@router.get(
    "/stations/{station_id}/weather/forecast",
    summary="Get weather forecast",
    description=(
        "Proxy the multi-day forecast for this station from OpenWeather, using "
        "the station's stored coordinates and metric units. Upstream failures "
        "surface as 502. Requires `OPENWEATHER_API_KEY` in the server environment."
    ),
)
async def get_station_weather_forecast(
    station_id: ValidStationId,
    user=Depends(get_optional_current_user),
) -> dict:
    require_station_view(station_id, user)
    lat, lon = camera_coordinates_for_weather(get_data_dir(), station_id)
    return await fetch_openweather("forecast", lat, lon, "metric")
