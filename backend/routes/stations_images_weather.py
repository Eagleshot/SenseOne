"""Weather and image serving routes."""

import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import read_camera_config, get_data_dir
from utils import media_type_from_path, sanitize_filename
from routes import ValidStationId

try:
    from mock_data import TIMEZONES
except ImportError:
    TIMEZONES = []


router = APIRouter(tags=["Stations"])


@router.get(
    "/timezones",
    tags=["System"],
    summary="List Timezones",
    description="Return the curated timezone options used by the frontend.",
)
def get_timezones() -> list[dict]:
    """Return list of available timezones."""
    return TIMEZONES


@router.get(
    "/stations/{station_id}/images/{filename}",
    summary="Get Station Image",
    description="Serve a stored image file for a specific station.",
)
def get_station_image(
    station_id: ValidStationId,
    filename: str,
) -> FileResponse:
    """Serve an image file for a station."""
    if filename != sanitize_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    data_dir = get_data_dir()
    image_path = data_dir / station_id / "images" / filename
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(image_path, media_type=media_type_from_path(image_path))


async def fetch_openweather(endpoint: str, lat: float, lon: float, units: str = "metric") -> dict:
    """Fetch data from OpenWeather API."""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OPENWEATHER_API_KEY.")
    
    url = f"https://api.openweathermap.org/data/2.5/{endpoint}"
    params = {"lat": lat, "lon": lon, "units": units, "appid": api_key}
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail="OpenWeather request failed.")
        return response.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail="OpenWeather request failed.") from exc


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
    summary="Get Current Weather",
    description="Fetch the current weather for a station using the station coordinates and metric units.",
)
async def get_station_current_weather(station_id: ValidStationId) -> dict:
    """Get current weather for a station."""
    lat, lon = camera_coordinates_for_weather(get_data_dir(), station_id)
    return await fetch_openweather("weather", lat, lon, "metric")


@router.get(
    "/stations/{station_id}/weather/forecast",
    summary="Get Weather Forecast",
    description="Fetch the weather forecast for a station using the station coordinates and metric units.",
)
async def get_station_weather_forecast(station_id: ValidStationId) -> dict:
    """Get weather forecast for a station."""
    lat, lon = camera_coordinates_for_weather(get_data_dir(), station_id)
    return await fetch_openweather("forecast", lat, lon, "metric")
