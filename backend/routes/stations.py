"""Station metadata and configuration routes."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from constants import DEFAULT_ONLINE_THRESHOLD_MINUTES, NEXT_ONLINE_STATUS_BUFFER_MINUTES
from models import (
    AppConfig,
    SensorHistoryResponse,
    StationCoordinates,
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
    get_data_dir,
    read_station_config,
    station_db_path,
    write_station_config,
)
from routes import ValidStationId
from station_access import (
    can_view_station,
    require_station_edit,
    require_station_view,
)
from station_db import history_from_db, image_captures_from_db, latest_status_from_db
from utils import humanize_station_id, iso_utc, parse_iso_timestamp, sanitize_station_id


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


def is_station_online(last_online: str | None, next_online: str | None, config: AppConfig) -> bool:
    """Return station online status from DB-backed runtime timestamps."""
    now = datetime.now(timezone.utc)
    next_online_at = parse_iso_timestamp(next_online)
    if next_online_at is not None:
        return now <= next_online_at + timedelta(minutes=NEXT_ONLINE_STATUS_BUFFER_MINUTES)

    last_online_at = parse_iso_timestamp(last_online)
    if last_online_at is None:
        return False
    threshold_minutes = max(config.capture_interval_minutes * 2, DEFAULT_ONLINE_THRESHOLD_MINUTES)
    return (now - last_online_at).total_seconds() <= threshold_minutes * 60


def station_status(
    base_dir: Path,
    station_id: str,
    config: AppConfig,
) -> tuple[bool, str | None, str | None, str | None, int | None]:
    """Get full station status. Returns (is_online, current_image, last_update, next_update, battery)."""
    capture, battery, last_online, next_online = latest_status_from_db(station_db_path(base_dir, station_id), station_id)

    latest = None
    if capture:
        timestamp = parse_iso_timestamp(capture["timestamp"])
        if timestamp is not None:
            latest = (timestamp, capture["url"])

    current_image = latest[1] if latest else None
    next_update = next_online

    if latest and next_update is None:
        captured_at, _ = latest
        next_update = iso_utc(captured_at + timedelta(minutes=config.capture_interval_minutes))

    return is_station_online(last_online, next_online, config), current_image, last_online, next_update, battery


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
        _, _, last_online, next_online = latest_status_from_db(station_db_path(data_dir, station_id), station_id)
        stations.append(
            StationSummaryResponse(
                id=station_id,
                name=config.title or humanize_station_id(station_id),
                location=config.location,
                country=config.country,
                country_emoji=config.country_emoji,
                coordinates=StationCoordinates(lat=config.lat, lng=config.lon, altitude=config.alt),
                is_public=config.is_public,
                is_online=is_station_online(last_online, next_online, config),
            )
        )
    return stations


@router.post(
    "/{station_id}/rotate-device-secret",
    response_model=StationDeviceSecretResponse,
    summary="Rotate station device HMAC secret",
    description=(
        "Mint a fresh 256-bit HMAC secret for the device(s) of this station and "
        "invalidate any previous one. Owner or admin only.\n\n"
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
    is_online, current_image, last_update, next_update, battery = station_status(data_dir, station_id, config)
    return StationDetailResponse(
        id=station_id,
        name=config.title or humanize_station_id(station_id),
        location=config.location,
        country=config.country,
        country_emoji=config.country_emoji,
        coordinates=StationCoordinates(lat=config.lat, lng=config.lon, altitude=config.alt),
        is_public=config.is_public,
        is_online=is_online,
        description=config.description,
        battery=battery,
        current_image=current_image,
        last_update=last_update,
        next_update=next_update,
    )


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
