"""Station metadata and configuration routes."""

from fastapi import APIRouter, Depends, Query

from models import AppConfig, ChartDataSource
from auth import get_current_username
from camera import (
    all_camera_ids,
    camera_summary,
    camera_detail,
    timeline_from_camera_db,
    timeline_from_image_dir,
    history_from_camera_db,
    chart_data_sources_from_camera_db,
)
from config import read_camera_config, write_camera_config, get_data_dir
from routes import ValidStationId


router = APIRouter(prefix="/stations", tags=["Stations"])


@router.get(
    "",
    summary="List Stations",
    description="Return the lightweight station overview used for the main station list, sidebar, and map.",
)
def list_stations() -> list[dict]:
    """Return summary of all stations."""
    data_dir = get_data_dir()
    return [camera_summary(data_dir, camera_id) for camera_id in all_camera_ids(data_dir)]


@router.get(
    "/{station_id}",
    summary="Get Station Detail",
    description="Return the detailed metadata and current status for a single station.",
)
def get_station(station_id: ValidStationId) -> dict:
    """Return detailed information for a station."""
    return camera_detail(get_data_dir(), station_id)


@router.get(
    "/{station_id}/timeline",
    summary="Get Station Timeline",
    description="Return the recent image timeline for a single station.",
)
def get_station_timeline(
    station_id: ValidStationId,
    count: int = Query(48, ge=1, le=240),
) -> list[dict]:
    """Return image timeline for a station."""
    data_dir = get_data_dir()
    timeline = timeline_from_camera_db(data_dir, station_id, count)
    if timeline is not None:
        return timeline
    return timeline_from_image_dir(data_dir, station_id, count)


@router.get(
    "/{station_id}/history",
    summary="Get Station History",
    description="Return sensor history rows for a single station from the station database.",
)
def get_station_history(
    station_id: ValidStationId,
    hours: int = Query(24, ge=1, le=168),
) -> list[dict]:
    """Return sensor history for a station."""
    return history_from_camera_db(get_data_dir(), station_id, hours) or []


@router.get(
    "/{station_id}/chart-data-sources",
    response_model=list[ChartDataSource],
    summary="Get Chart Data Sources",
    description="Return the selectable chart data sources configured for a station.",
)
def get_station_chart_data_sources(station_id: ValidStationId) -> list[ChartDataSource]:
    """Return chart data sources for a station."""
    return chart_data_sources_from_camera_db(get_data_dir(), station_id) or []


@router.get(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Get Station Config",
    description="Return the persisted configuration for one station.",
)
def get_station_config(
    station_id: ValidStationId,
    _: str = Depends(get_current_username),
) -> AppConfig:
    """Return configuration for a station."""
    return read_camera_config(get_data_dir(), station_id)


@router.put(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Update Station Config",
    description="Replace the persisted configuration for one station.",
)
def update_station_config(
    station_id: ValidStationId,
    payload: AppConfig,
    _: str = Depends(get_current_username),
) -> AppConfig:
    """Update configuration for a station."""
    write_camera_config(get_data_dir(), station_id, payload)
    return payload
