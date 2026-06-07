"""Weather and image serving routes."""

import base64
import os
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

import store
from auth import get_optional_current_user
from config import get_data_dir
from station_access import require_station_view
from utils import media_type_from_path, sanitize_filename
from routes import ValidStationId


router = APIRouter(tags=["Stations"])

# OpenWeather Maps 1.0 overlay layers we allow proxying (the "_new" styled tiles).
WEATHER_TILE_LAYERS = {
    "clouds_new",
    "precipitation_new",
    "temp_new",
    "wind_new",
    "pressure_new",
}

# A map view fires off dozens of tile requests at once. Reuse one pooled client
# with HTTP keep-alive so we don't pay a fresh TLS handshake to OpenWeather per
# tile (the main source of overlay slowness).
_tile_client: "httpx.AsyncClient | None" = None


def _weather_tile_client() -> httpx.AsyncClient:
    global _tile_client
    if _tile_client is None or _tile_client.is_closed:
        _tile_client = httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
        )
    return _tile_client


class TTLCache:
    """Process-wide, size-bounded cache of values with per-entry expiry.

    Stored as key -> (expiry_monotonic, value). Caching one upstream OpenWeather
    response and replaying it for the refresh window collapses many viewers'
    identical requests into a single upstream call (the main cost lever). On
    overflow we drop expired entries first, then the oldest by insertion order.
    Not thread-safe, but the async routes that use it don't await between get/put.
    """

    def __init__(self, max_entries: int):
        self._max_entries = max_entries
        self._store: dict = {}

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, value = entry
        if expiry < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    def put(self, key, value, ttl: float) -> None:
        if len(self._store) >= self._max_entries:
            now = time.monotonic()
            for stale in [k for k, (expiry, _) in self._store.items() if expiry < now]:
                self._store.pop(stale, None)
            while len(self._store) >= self._max_entries:
                self._store.pop(next(iter(self._store)), None)  # drop oldest insertion
        self._store[key] = (time.monotonic() + ttl, value)


# Tile cache: low-zoom world tiles are identical for everyone; cache value is
# (content_bytes, media_type). 4000 entries ~= a few viewers' worth of panning.
_TILE_CACHE_TTL = 600  # seconds; OpenWeather refreshes these layers ~every 10 min
_tile_cache = TTLCache(max_entries=4000)


# A 1x1 transparent PNG served (and cached) for tiles OpenWeather has no data for,
# so the overlay just shows nothing there instead of erroring out.
_TRANSPARENT_TILE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# Weather data cache (current weather / forecast), keyed by endpoint+coords+units;
# cache value is the parsed JSON dict. TTL is supplied per put by the caller.
_weather_data_cache = TTLCache(max_entries=500)


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


async def fetch_openweather(
    endpoint: str, lat: float, lon: float, units: str = "metric", cache_ttl: int = 600
) -> dict:
    """Fetch data from OpenWeather API, cached per (endpoint, coordinates, units).

    Results are cached for ``cache_ttl`` seconds so repeated viewers of the same
    station don't each trigger an upstream call. Upstream non-2xx responses are
    surfaced as 502 (bad gateway) so the client cannot mistake them for problems
    with this service. The underlying status is logged for diagnostics.
    """
    import logging

    cache_key = (endpoint, round(lat, 3), round(lon, 3), units)
    cached = _weather_data_cache.get(cache_key)
    if cached is not None:
        return cached

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

    data = response.json()
    _weather_data_cache.put(cache_key, data, cache_ttl)
    return data


def station_coordinates_for_weather(station_id: str) -> tuple[float, float]:
    """Get coordinates for weather API calls."""
    config = store.station_config(station_id)
    lat = config.lat
    lon = config.lon
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Station coordinates are invalid.")
    if lat == 0 and lon == 0:
        raise HTTPException(status_code=400, detail="Station coordinates are not configured.")
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
    lat, lon = station_coordinates_for_weather(station_id)
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
    lat, lon = station_coordinates_for_weather(station_id)
    return await fetch_openweather("forecast", lat, lon, "metric", cache_ttl=1800)


@router.get(
    "/weather/map/{layer}/{z}/{x}/{y}",
    summary="Get a weather map overlay tile",
    description=(
        "Proxy an OpenWeather Maps 1.0 overlay tile (clouds / precipitation / "
        "temperature / wind / pressure) so the API key stays server-side. Returns "
        "a PNG tile; upstream failures surface as 502. The overlay is shown on the "
        "public station map, so this endpoint is unauthenticated like the base map "
        "tiles. Requires `OPENWEATHER_API_KEY` in the server environment."
    ),
)
async def get_weather_map_tile(layer: str, z: int, x: int, y: int) -> Response:
    import logging

    if layer not in WEATHER_TILE_LAYERS:
        raise HTTPException(status_code=404, detail="Unknown weather layer.")

    cache_key = (layer, z, x, y)
    cached = _tile_cache.get(cache_key)
    if cached is not None:
        content, media_type = cached
        return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=900"})

    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OPENWEATHER_API_KEY.")

    url = f"https://tile.openweathermap.org/map/{layer}/{z}/{x}/{y}.png"
    try:
        response = await _weather_tile_client().get(url, params={"appid": api_key})
    except httpx.RequestError as exc:
        logging.warning("OpenWeather tile request error: %s", exc)
        raise HTTPException(status_code=502, detail="OpenWeather tile request failed.") from exc

    # OpenWeather returns 404 for tiles it has no data for in this layer (e.g.
    # empty ocean/land areas). That's expected, not a failure: serve a transparent
    # tile and cache it so repeat pans/zooms don't re-hit upstream.
    if response.status_code == 404:
        logging.debug("OpenWeather tile has no data (404): %s/%s/%s/%s", layer, z, x, y)
        _tile_cache.put(cache_key, (_TRANSPARENT_TILE, "image/png"), _TILE_CACHE_TTL)
        return Response(
            content=_TRANSPARENT_TILE,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=900"},
        )

    if response.status_code >= 400:
        logging.warning("OpenWeather tile upstream returned %s for %s", response.status_code, layer)
        raise HTTPException(status_code=502, detail="OpenWeather tile request failed.")

    media_type = response.headers.get("content-type", "image/png")
    _tile_cache.put(cache_key, (response.content, media_type), _TILE_CACHE_TTL)
    return Response(
        content=response.content,
        media_type=media_type,
        # Cache in the browser too so panning/zoom revisits are instant.
        headers={"Cache-Control": "public, max-age=900"},
    )
