"""Station metadata and configuration routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, status

import store
from constants import NEXT_ONLINE_STATUS_BUFFER_MINUTES
from models import (
    AppConfig,
    SensorSeries,
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
from station_db import StationStatus
from routes import ValidStationId
from station_access import (
    can_edit_station,
    require_station_edit,
    require_station_view,
)
from utils import humanize_station_id, parse_iso_timestamp


router = APIRouter(prefix="/stations", tags=["Stations"])


def is_station_online(next_online: str | None) -> bool:
    """Determine if a station is currently online based on its next_online timestamp."""
    next_online_at = parse_iso_timestamp(next_online)
    if next_online_at is None:
        return False
    return datetime.now(timezone.utc) <= next_online_at + timedelta(minutes=NEXT_ONLINE_STATUS_BUFFER_MINUTES)


def station_detail_response(
    public_id: str, url_slug: str, config: AppConfig, status: StationStatus, can_edit: bool
) -> StationDetailResponse:
    """Build a station detail response from config plus latest runtime status."""
    return StationDetailResponse(
        id=public_id,
        url_slug=url_slug,
        name=config.title or humanize_station_id(url_slug),
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
        can_edit=can_edit,
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
    return [
        StationSummaryResponse(
            id=public_id,
            url_slug=url_slug,
            name=config.title or humanize_station_id(url_slug),
            location=config.location,
            country=config.country,
            country_emoji=config.country_emoji,
            coordinates=StationCoordinates(lat=config.lat, lng=config.lon, altitude=config.alt),
            is_public=config.is_public,
            is_online=is_station_online(status.next_online),
            can_edit=can_edit,
        )
        for public_id, url_slug, config, status, can_edit in store.list_station_views(user)
    ]


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
    public_id = store.create_station(payload, user)
    view = store.station_view(public_id)
    assert view is not None  # just created
    url_slug, config, status = view
    # The creator owns the station, so they can always edit it.
    return station_detail_response(public_id, url_slug, config, status, can_edit=True)


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
    view = store.station_view(station_id)
    assert view is not None  # require_station_view already confirmed it exists
    url_slug, config, status = view
    return station_detail_response(
        station_id, url_slug, config, status, can_edit=can_edit_station(station_id, user)
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
    rows = store.image_captures(station_id, count)
    return [TimelineItemResponse(**row) for row in rows]


@router.get(
    "/{station_id}/sensor-readings",
    response_model=list[SensorSeries],
    summary="Get sensor readings",
    description=(
        "Sensor history for this station from the configured lookback window, as "
        "one point series per (metric, channel). `hours` controls the window "
        "(default 24, max 168 = 7 days). Returns an empty list if the station has "
        "no readings yet."
    ),
)
def get_station_sensor_readings(
    station_id: ValidStationId,
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours."),
    user=Depends(get_optional_current_user),
) -> list[SensorSeries]:
    require_station_view(station_id, user)
    series = store.sensor_readings(station_id, hours)
    return [SensorSeries(**item) for item in series]


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
    return store.station_config(station_id)


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
    store.save_station_config(station_id, payload)
    # Re-read so the response matches GET /config (including the derived
    # lastOnline/nextOnline status), rather than echoing the request body.
    return store.station_config(station_id)
