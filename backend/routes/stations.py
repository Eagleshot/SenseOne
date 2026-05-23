"""Station metadata and configuration routes."""

from fastapi import APIRouter, Depends, Query

from models import (
    AppConfig,
    SensorHistoryResponse,
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
from station_repository import (
    image_captures,
    list_station_ids,
    sensor_history,
    station_detail,
    station_summary,
)
from config import (
    get_data_dir,
    read_camera_config,
    write_camera_config,
)
from routes import ValidStationId
from station_access import (
    can_view_station,
    require_station_edit,
    require_station_view,
)


router = APIRouter(prefix="/stations", tags=["Stations"])


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
def list_stations(user=Depends(get_optional_current_user)) -> list[dict]:
    data_dir = get_data_dir()
    visible = [station_id for station_id in list_station_ids(data_dir) if can_view_station(station_id, user)]
    return [station_summary(data_dir, station_id) for station_id in visible]


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
) -> dict:
    require_station_view(station_id, user)
    return station_detail(get_data_dir(), station_id)


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
) -> list[dict]:
    require_station_view(station_id, user)
    return image_captures(get_data_dir(), station_id, count) or []


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
) -> list[dict]:
    require_station_view(station_id, user)
    return sensor_history(get_data_dir(), station_id, hours) or []


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
    return read_camera_config(get_data_dir(), station_id)


@router.put(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Update station config",
    description=(
        "Replace the persisted configuration document for one station. "
        "Owner or admin only. Returns 422 if validation fails (e.g. "
        "`cameraStartTime` not earlier than `cameraStopTime`)."
    ),
)
def update_station_config(
    station_id: ValidStationId,
    payload: AppConfig,
    user=Depends(get_current_user),
) -> AppConfig:
    require_station_edit(station_id, user)
    write_camera_config(get_data_dir(), station_id, payload)
    return payload
