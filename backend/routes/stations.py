"""Station metadata and configuration routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from pydantic import ValidationError

from api_docs import IMAGE_RESPONSE_CONTENT, error_response
from constants import NEXT_ONLINE_STATUS_BUFFER_MINUTES
from db import station_repo
from image_store import get_image_store
from models import (
    AppConfig,
    AppConfigUpdate,
    SensorReadingEnvelope,
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
from utils import humanize_station_id, media_type_from_path, parse_iso_timestamp, sanitize_filename


router = APIRouter(prefix="/stations", tags=["Stations"])


def is_station_online(next_online: str | None) -> bool:
    """Determine if a station is currently online based on its next_online timestamp."""
    next_online_at = parse_iso_timestamp(next_online)
    if next_online_at is None:
        return False
    return datetime.now(timezone.utc) <= next_online_at + timedelta(minutes=NEXT_ONLINE_STATUS_BUFFER_MINUTES)


def _station_base_fields(
    public_id: str, url_slug: str, config: AppConfig, status: StationStatus, can_edit: bool
) -> dict:
    """Response fields shared by the station summary and detail schemas."""
    return dict(
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


def station_detail_response(
    public_id: str, url_slug: str, config: AppConfig, status: StationStatus, can_edit: bool
) -> StationDetailResponse:
    """Build a station detail response from config plus latest runtime status."""
    return StationDetailResponse(
        **_station_base_fields(public_id, url_slug, config, status, can_edit),
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
    return [
        StationSummaryResponse(**_station_base_fields(public_id, url_slug, config, status, can_edit))
        for public_id, url_slug, config, status, can_edit in station_repo.list_station_views(user)
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
    responses={
        401: error_response("A valid session is required."),
        503: error_response("Authentication is unavailable."),
    },
)
def create_station(
    payload: StationCreateRequest,
    user=Depends(get_current_user),
) -> StationDetailResponse:
    public_id = station_repo.create_station(payload, user.owner_id)
    view = station_repo.station_view(public_id)
    assert view is not None  # just created
    url_slug, config, status = view
    # The creator owns the station, so they can always edit it.
    return station_detail_response(public_id, url_slug, config, status, can_edit=True)


@router.post(
    "/{station_id}/rotate-device-secret",
    response_model=StationDeviceSecretResponse,
    summary="Rotate station device HMAC secret",
    description=(
        "Create a new device HMAC secret and invalidate the previous one. The "
        "returned secret is shown once and must be provisioned on the device."
    ),
    responses={
        401: error_response("A valid session is required."),
        403: error_response("Station edit access is required."),
        404: error_response("The station was not found."),
        503: error_response("Authentication is unavailable."),
    },
)
def rotate_station_device_secret(
    station_id: ValidStationId,
    user=Depends(get_current_user),
) -> StationDeviceSecretResponse:
    require_station_edit(station_id, user)
    secret_b64 = provision_device_hmac_secret(station_id)
    return StationDeviceSecretResponse(station_id=station_id, device_hmac_secret=secret_b64)


@router.delete(
    "/{station_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete station",
    description="Permanently delete a station and its associated data.",
    responses={
        401: error_response("A valid session is required."),
        403: error_response("Station edit access is required."),
        404: error_response("The station was not found."),
        503: error_response("Authentication is unavailable."),
    },
)
def delete_station(
    station_id: ValidStationId,
    user=Depends(get_current_user),
) -> Response:
    require_station_edit(station_id, user)
    # DB row first (cascades take the child rows), then the blobs. If blob
    # cleanup dies halfway the worst case is orphan files, which a future
    # retention sweep can reap — never a DB row pointing at deleted blobs.
    station_repo.delete_station(station_id)
    get_image_store().delete_prefix(station_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{station_id}",
    response_model=StationDetailResponse,
    summary="Get station detail",
    description="Return metadata and current status for an accessible station.",
    responses={404: error_response("The station was not found.")},
)
def get_station(
    station_id: ValidStationId,
    user=Depends(get_optional_current_user),
) -> StationDetailResponse:
    require_station_view(station_id, user)
    view = station_repo.station_view(station_id)
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
    responses={404: error_response("The station was not found.")},
)
def get_station_image_captures(
    station_id: ValidStationId,
    count: int = Query(48, ge=1, le=240, description="Maximum number of captures to return."),
    user=Depends(get_optional_current_user),
) -> list[TimelineItemResponse]:
    require_station_view(station_id, user)
    rows = station_repo.image_captures(station_id, count)
    return [TimelineItemResponse(**row) for row in rows]


@router.get(
    "/{station_id}/images/{filename}",
    response_class=FileResponse,
    summary="Get station image",
    description="Return an image named by the station's image-captures response.",
    responses={
        200: {"description": "JPEG, PNG, or WebP image.", "content": IMAGE_RESPONSE_CONTENT},
        400: error_response("The filename is invalid."),
        404: error_response("The station or image was not found."),
    },
)
def get_station_image(
    station_id: ValidStationId,
    filename: str,
    user=Depends(get_optional_current_user),
) -> FileResponse:
    if filename != sanitize_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    require_station_view(station_id, user)
    # The DB row's storage_key is the source of truth: a blob is only served if
    # its metadata row exists, and the stored key decides where the blob lives.
    storage_key = station_repo.image_storage_key(station_id, filename)
    if storage_key is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    image_path = get_image_store().path(storage_key)
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    # Cache policy by station visibility. Public captures are immutable in
    # practice, so browsers may reuse them for a day without revalidating every
    # timeline scrub. Private captures instead force revalidation: the conditional
    # request re-reaches the server and re-runs the access check, so a cached blob
    # can't be replayed after the user logs out or switches accounts.
    # An anonymous caller only gets past require_station_view for a public station,
    # so the extra visibility query is paid only for authenticated callers.
    is_public = user is None or station_repo.can_view(station_id, None)
    if is_public:
        cache_control = "private, max-age=86400"
    else:
        cache_control = "private, no-cache"
    return FileResponse(
        image_path,
        media_type=media_type_from_path(image_path),
        headers={"Cache-Control": cache_control},
    )


@router.get(
    "/{station_id}/data",
    response_model=list[SensorSeries],
    summary="Get sensor readings",
    description=(
        "Sensor history for this station from the configured lookback window, as "
        "one point series per (metric, channel). `hours` controls the window "
        "(default 24). Returns an empty list if the station has no readings yet."
    ),
    responses={404: error_response("The station was not found.")},
)
def get_station_sensor_readings(
    station_id: ValidStationId,
    hours: int = Query(24, ge=1, description="Lookback window in hours."),
    user=Depends(get_optional_current_user),
) -> list[SensorSeries]:
    require_station_view(station_id, user)
    series = station_repo.sensor_readings(station_id, hours)
    return [SensorSeries(**item) for item in series]


@router.get(
    "/{station_id}/readings",
    response_model=list[SensorReadingEnvelope],
    summary="Get sensor reading envelopes",
    description=(
        "Per-reading envelopes for this station from the lookback window: one entry "
        "per device check-in with its timestamp, next-online hint, firmware version, "
        "and wake reason. Unlike `/data` (which is keyed off measurements), this "
        "includes check-ins that reported no metrics. `hours` controls the window "
        "(default 24). Empty list if the station has no readings yet."
    ),
    responses={404: error_response("The station was not found.")},
)
def get_station_reading_envelopes(
    station_id: ValidStationId,
    hours: int = Query(24, ge=1, description="Lookback window in hours."),
    user=Depends(get_optional_current_user),
) -> list[SensorReadingEnvelope]:
    require_station_view(station_id, user)
    envelopes = station_repo.sensor_reading_envelopes(station_id, hours)
    return [SensorReadingEnvelope(**item) for item in envelopes]


@router.get(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Get station config",
    description="Return the editable configuration for a station.",
    responses={
        401: error_response("A valid session is required."),
        403: error_response("Station edit access is required."),
        404: error_response("The station was not found."),
        503: error_response("Authentication is unavailable."),
    },
)
def get_station_config(
    station_id: ValidStationId,
    user=Depends(get_current_user),
) -> AppConfig:
    require_station_edit(station_id, user)
    return station_repo.station_config(station_id) or AppConfig()


@router.put(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Update station config",
    description=(
        "Update a station configuration. Omitted fields keep their current values; "
        "`alt` may be null to represent an unknown altitude."
    ),
    responses={
        401: error_response("A valid session is required."),
        403: error_response("Station edit access is required."),
        404: error_response("The station was not found."),
        503: error_response("Authentication is unavailable."),
    },
)
def update_station_config(
    station_id: ValidStationId,
    payload: AppConfigUpdate,
    user=Depends(get_current_user),
) -> AppConfig:
    require_station_edit(station_id, user)
    try:
        station_repo.save_station_config(station_id, payload)
    except ValidationError as exc:
        # Per-field validation passed, but merging into the stored document
        # broke a cross-field rule (checked only on the merged result).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=jsonable_encoder(exc.errors()),
        ) from exc
    # Re-read so the response reflects the persisted, normalized config (e.g. a
    # title-driven slug change) rather than echoing the request body.
    return station_repo.station_config(station_id) or AppConfig()
