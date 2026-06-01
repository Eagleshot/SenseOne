"""Station metadata and configuration routes."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from constants import NEXT_ONLINE_STATUS_BUFFER_MINUTES
from models import (
    AppConfig,
    SensorHistoryResponse,
    StationCoordinates,
    StationCreateRequest,
    StationDetailResponse,
    StationDeviceSecretResponse,
    StationSummaryResponse,
    TimelineItemResponse,
)
from station_hmac import provision_device_hmac_secret
from auth import (
    get_current_user,
    get_optional_current_user,
)
from config import (
    ensure_station_dir,
    get_data_dir,
    read_station_config,
    station_db_path,
    write_station_meta,
    write_station_config,
)
from routes import ValidStationId
from station_access import (
    can_view_station,
    require_station_edit,
    require_station_view,
)
from station_db import history_from_db, image_captures_from_db, latest_status_from_db
from utils import humanize_station_id, parse_iso_timestamp, sanitize_station_id, unique_station_id


router = APIRouter(prefix="/stations", tags=["Stations"])


def list_station_ids(base_dir: Path) -> list[str]:
    """Get ordered list of station IDs from the data directory."""
    if not base_dir.exists():
        return []

    seen: set[str] = set()
    station_ids: list[str] = []
    for child in sorted(base_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        station_id = sanitize_station_id(child.name)
        if station_id not in seen:
            station_ids.append(station_id)
            seen.add(station_id)
    return station_ids


def is_station_online(next_online: str | None) -> bool:
    """Determine if a station is currently online based on its next_online timestamp."""
    next_online_at = parse_iso_timestamp(next_online)
    if next_online_at is None:
        return False
    return datetime.now(timezone.utc) <= next_online_at + timedelta(minutes=NEXT_ONLINE_STATUS_BUFFER_MINUTES)


def station_detail_response(data_dir: Path, station_id: str, config: AppConfig) -> StationDetailResponse:
    """Build a station detail response from config plus latest runtime status."""
    status = latest_status_from_db(station_db_path(data_dir, station_id), station_id)
    return StationDetailResponse(
        id=station_id,
        name=config.title or humanize_station_id(station_id),
        location=config.location,
        country=config.country,
        country_emoji=config.country_emoji,
        coordinates=StationCoordinates(lat=config.lat, lng=config.lon, altitude=config.alt),
        is_public=config.is_public,
        is_online=is_station_online(status.next_online),
        description=config.description,
        battery=status.battery,
        current_image=status.capture["url"] if status.capture else None,
        last_update=status.last_online,
        next_update=status.next_online,
        firmware_version=status.firmware_version,
        wake_reason=status.wake_reason,
    )


@router.get(
    "",
    response_model=list[StationSummaryResponse],
    summary="List stations",
    description=(
        "Lightweight overview of every station the caller is allowed to see. "
        "Anonymous callers get the public stations only; authenticated users "
        "also see private stations they own."
    ),
)
def list_stations(user=Depends(get_optional_current_user)) -> list[StationSummaryResponse]:
    data_dir = get_data_dir()
    stations = []
    for station_id in list_station_ids(data_dir):
        config = read_station_config(data_dir, station_id)
        if not can_view_station(station_id, user, config):
            continue
        next_online = latest_status_from_db(station_db_path(data_dir, station_id), station_id).next_online
        stations.append(
            StationSummaryResponse(
                id=station_id,
                name=config.title or humanize_station_id(station_id),
                location=config.location,
                country=config.country,
                country_emoji=config.country_emoji,
                coordinates=StationCoordinates(lat=config.lat, lng=config.lon, altitude=config.alt),
                is_public=config.is_public,
                is_online=is_station_online(next_online),
            )
        )
    return stations


@router.post(
    "",
    response_model=StationDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create station",
    description=(
        "Create a new station owned by the authenticated user. The station id "
        "is derived from the title and made unique automatically."
    ),
)
def create_station(
    payload: StationCreateRequest,
    user=Depends(get_current_user),
) -> StationDetailResponse:
    data_dir = get_data_dir()
    station_id = unique_station_id(data_dir, payload.title, default="station")
    if station_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create a unique station id.",
        )
    config = AppConfig(
        title=payload.title,
        location=payload.location,
        country=payload.country,
        country_emoji=payload.country_emoji,
        lat=payload.lat,
        lon=payload.lon,
        alt=payload.alt,
        is_public=payload.is_public,
    )

    ensure_station_dir(data_dir, station_id)
    write_station_config(data_dir, station_id, config)
    write_station_meta(data_dir, station_id, owner=user.username)

    return station_detail_response(data_dir, station_id, config)


@router.post(
    "/{station_id}/rotate-device-secret",
    response_model=StationDeviceSecretResponse,
    summary="Rotate station device HMAC secret",
    description=(
        "Mint a fresh 256-bit HMAC secret for the device(s) of this station and "
        "invalidate any previous one. Owner only.\n\n"
        "The returned `deviceHmacSecret` is shown **exactly once** — flash it to "
        "the device and discard the response. Subsequent device requests must "
        "sign each call with this secret (see the `hmacSignature` auth scheme)."
    ),
)
def rotate_station_device_secret(
    station_id: ValidStationId,
    user=Depends(get_current_user),
) -> StationDeviceSecretResponse:
    require_station_edit(station_id, user)
    secret_b64 = provision_device_hmac_secret(station_id)
    return StationDeviceSecretResponse(station_id=station_id, device_hmac_secret=secret_b64)


@router.get(
    "/{station_id}",
    response_model=StationDetailResponse,
    summary="Get station detail",
    description=(
        "Detailed metadata and current status for one station. Returns 404 to "
        "anonymous callers if the station is private."
    ),
)
def get_station(
    station_id: ValidStationId,
    user=Depends(get_optional_current_user),
) -> StationDetailResponse:
    require_station_view(station_id, user)
    data_dir = get_data_dir()
    config = read_station_config(data_dir, station_id)
    return station_detail_response(data_dir, station_id, config)


@router.get(
    "/{station_id}/image-captures",
    response_model=list[TimelineItemResponse],
    summary="Get recent image captures",
    description=(
        "Most-recent image captures for this station, oldest-to-newest. The `count` "
        "query parameter caps the page size (default 48, max 240)."
    ),
)
def get_station_image_captures(
    station_id: ValidStationId,
    count: int = Query(48, ge=1, le=240, description="Maximum number of captures to return."),
    user=Depends(get_optional_current_user),
) -> list[TimelineItemResponse]:
    require_station_view(station_id, user)
    data_dir = get_data_dir()
    rows = image_captures_from_db(station_db_path(data_dir, station_id), station_id, count)
    return [TimelineItemResponse(**row) for row in rows]


@router.get(
    "/{station_id}/sensor-readings",
    response_model=list[SensorHistoryResponse],
    summary="Get sensor readings",
    description=(
        "Sensor history for this station from the configured lookback window. "
        "`hours` controls the window (default 24, max 168 = 7 days). Returns "
        "an empty list if the station has no readings yet."
    ),
)
def get_station_sensor_readings(
    station_id: ValidStationId,
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours."),
    user=Depends(get_optional_current_user),
) -> list[SensorHistoryResponse]:
    require_station_view(station_id, user)
    data_dir = get_data_dir()
    rows = history_from_db(station_db_path(data_dir, station_id), station_id, hours)
    return [SensorHistoryResponse(**row) for row in rows]


@router.get(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Get station config",
    description=(
        "Return the persisted configuration document for one station. "
        "Owner or admin only."
    ),
)
def get_station_config(
    station_id: ValidStationId,
    user=Depends(get_current_user),
) -> AppConfig:
    require_station_edit(station_id, user)
    return read_station_config(get_data_dir(), station_id)


@router.put(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Update station config",
    description=(
        "Replace the persisted configuration document for one station. "
        "Owner or admin only. Returns 422 if validation fails (e.g. "
        "`stationStartTime` not earlier than `stationStopTime`)."
    ),
)
def update_station_config(
    station_id: ValidStationId,
    payload: AppConfig,
    user=Depends(get_current_user),
) -> AppConfig:
    require_station_edit(station_id, user)
    write_station_config(get_data_dir(), station_id, payload)
    return payload
