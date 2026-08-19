"""HMAC-signed device ingestion routes."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from api_docs import RAW_IMAGE_REQUEST_BODY, SENSOR_INGESTION_EXAMPLE, error_response
from constants import ALLOWED_IMAGE_EXTENSIONS
from db import station_repo
from image_store import LocalDiskImageStore, get_image_store, station_image_key
from models import AppConfig, DeviceConfig, ImageUploadResponse, SensorReadingRequest
from routes import ValidStationId
from settings import get_settings
from station_access import require_station_exists
from station_hmac import verify_station_signature
from utils import (
    default_capture_filename,
    image_timestamp_from_filename,
    inject_name_if_missing,
    is_supported_image_upload,
    iso_utc,
    media_type_from_path,
    sanitize_filename,
    without_non_finite_floats,
)

# Body cap for the signed non-image routes (config has no body; a maximal data
# check-in is tens of KB of JSON). Far below the image cap, so an unauthenticated
# caller can't buffer megabytes through these endpoints.
MAX_JSON_BODY_BYTES = 1 * 1024 * 1024


def _enforce_free_disk(image_store: LocalDiskImageStore, incoming_bytes: int) -> None:
    """Reject uploads with 507 when storing this body would breach the floor.

    The floor (APP_MIN_FREE_DISK_BYTES, default 500 MiB, 0 disables) is a safety
    valve, not per-plan retention: a device with a valid secret (or a buggy one)
    could otherwise loop uploads and fill the disk, which takes the whole service
    down and can corrupt in-flight SQLite writes.
    """
    min_free = get_settings().min_free_disk_bytes
    if min_free <= 0:
        return
    free = image_store.free_bytes()
    if free is None:
        return
    if free - incoming_bytes < min_free:
        logging.error(
            "Refusing upload: free disk %d would drop below floor %d after %d bytes.",
            free, min_free, incoming_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Server storage is full. Upload rejected.",
        )

router = APIRouter(prefix="/stations", tags=["Device ingestion"])

# Error responses common to every signed device route, surfaced in the OpenAPI
# schema. Each route spreads this and adds the failures specific to its payload.
# Note: no 404 — an unknown station id 401s like a station without a secret, so
# unauthenticated callers can't probe which station ids exist.
_SIGNED_REQUEST_ERRORS: dict[int | str, dict] = {
    400: error_response("The station id is malformed."),
    401: error_response("HMAC authentication failed."),
}


def store_uploaded_image(
    station_id: str,
    filename: str,
    body: bytes,
    content_type: str | None,
) -> tuple[str, str]:
    """Persist an uploaded image that has already passed HMAC verification."""
    max_upload_bytes = get_settings().max_upload_bytes
    if not is_supported_image_upload(filename, content_type):
        supported = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type. Allowed extensions: {supported}",
        )
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if len(body) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload too large. Maximum is {max_upload_bytes} bytes.",
        )

    image_store = get_image_store()
    require_station_exists(station_id)
    _enforce_free_disk(image_store, len(body))

    image_timestamp = image_timestamp_from_filename(filename)
    if image_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Filename must match YYYYMMDD_HHMMZ_<camera>.jpg.",
        )

    stored_filename = filename
    storage_key = station_image_key(station_id, stored_filename)

    try:
        image_store.save(storage_key, body)
        detected_media_type = media_type_from_path(image_store.path(storage_key))
        if detected_media_type is None:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File contents are not a recognised image.",
            )
    except HTTPException:
        image_store.delete(storage_key)
        raise

    station_repo.append_image(
        station_id,
        filename=stored_filename,
        content_type=detected_media_type,
        size_bytes=len(body),
        captured_at=iso_utc(image_timestamp),
    )
    return stored_filename, f"/stations/{station_id}/images/{stored_filename}"


def _hhmm_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


@router.get(
    "/{station_id}/config",
    response_model=DeviceConfig,
    summary="Get station config for a device",
    description=(
        "Return the capture schedule and location required for the device's next "
        "wake cycle. This request has no body."
    ),
    responses=_SIGNED_REQUEST_ERRORS,
)
async def get_device_station_config(
    station_id: ValidStationId,
    request: Request,
) -> DeviceConfig:
    await verify_station_signature(station_id, request, max_body_bytes=MAX_JSON_BODY_BYTES)
    config = station_repo.station_config(station_id) or AppConfig()
    return DeviceConfig(
        station_start_minute=_hhmm_to_minutes(config.station_start_time),
        station_stop_minute=_hhmm_to_minutes(config.station_stop_time),
        use_sunrise_sunset=config.use_sunrise_sunset,
        capture_interval_minutes=config.capture_interval_minutes,
        lat=config.lat,
        lon=config.lon,
        # Firmware expects a plain number; an unknown altitude degrades to 0.0
        # (only feeds the optional sunrise/sunset computation, where the error
        # is negligible).
        alt=config.alt if config.alt is not None else 0.0,
        name=station_repo.station_name_token(station_id),
    )


@router.post(
    "/{station_id}/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one image",
    description=(
        "Upload raw JPEG, PNG, or WebP bytes. `X-Filename`, when supplied, must "
        "contain the UTC capture minute and camera name."
    ),
    responses={
        **_SIGNED_REQUEST_ERRORS,
        400: error_response("The upload is empty or malformed."),
        413: error_response("The upload is too large."),
        415: error_response("The image type is unsupported or unrecognized."),
        422: error_response("X-Filename must match YYYYMMDD_HHMMZ_<camera>.<ext>."),
        507: error_response("The upload could not be stored."),
    },
    openapi_extra=RAW_IMAGE_REQUEST_BODY,
)
async def upload_station_image(
    station_id: ValidStationId,
    request: Request,
    x_filename: str | None = Header(
        default=None,
        description=(
            "Optional capture filename in `YYYYMMDD_HHMMZ_<camera>.<ext>` format. "
            "Its exact value is included in the HMAC signing string."
        ),
    ),
) -> ImageUploadResponse:
    max_upload_bytes = get_settings().max_upload_bytes
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_value = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length header.") from exc
        if content_length_value > max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload too large. Maximum is {max_upload_bytes} bytes.",
            )

    body = await verify_station_signature(station_id, request, max_body_bytes=max_upload_bytes)
    content_type = request.headers.get("content-type")
    # X-Filename is optional: a device may omit it (or send blank), and the server
    # stamps a capture name from the current UTC minute. The station's frozen name
    # token is injected so the stored file (hence the dashboard download) is
    # self-identifying: an omitted/bare-timestamp name becomes
    # YYYYMMDD_HHMMZ_<name>.jpg; a name the device already supplied is kept as-is.
    # A supplied name must still match the capture format (store_uploaded_image enforces it).
    name_token = station_repo.station_name_token(station_id)
    provided_name = (x_filename or "").strip()
    filename = (
        inject_name_if_missing(sanitize_filename(provided_name), name_token)
        if provided_name
        else default_capture_filename(content_type, name=name_token)
    )
    stored_filename, image_url = store_uploaded_image(
        station_id=station_id,
        filename=filename,
        body=body,
        content_type=content_type,
    )
    logging.info("File saved for station %s as %s", station_id, stored_filename)
    return ImageUploadResponse(filename=stored_filename, url=image_url)


@router.post(
    "/{station_id}/data",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Upload one device check-in",
    description=(
        "Upload a JSON check-in with optional device metadata and a `readings` array. "
        "Each reading contains an optional channel and numeric measurements. Returns "
        "204 with no response body."
    ),
    responses={
        **_SIGNED_REQUEST_ERRORS,
        413: error_response("The request body is too large."),
        422: error_response("The request body is invalid."),
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": SensorReadingRequest.model_json_schema(),
                    "example": SENSOR_INGESTION_EXAMPLE,
                }
            },
        }
    },
)
async def create_sensor_reading(
    station_id: ValidStationId,
    request: Request,
) -> Response:
    # Verify the signature before parsing the body so an unauthenticated caller
    # can't trigger full Pydantic validation (matches the image route's verify-first
    # ordering). The body param is documented via openapi_extra above instead.
    body = await verify_station_signature(station_id, request, max_body_bytes=MAX_JSON_BODY_BYTES)
    try:
        payload = SensorReadingRequest.model_validate_json(body)
    except ValidationError as exc:
        # The echoed input can contain non-finite floats (a device posting
        # 1e999/NaN); unsanitized they crash the 422 render into a 500.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=without_non_finite_floats(jsonable_encoder(exc.errors())),
        ) from exc
    timestamp = payload.timestamp or iso_utc(datetime.now(timezone.utc))
    channel_metrics = [(reading.resolved_channel, reading.metrics) for reading in payload.readings]
    station_repo.append_reading(
        station_id,
        timestamp,
        channel_metrics,
        firmware_version=payload.firmware_version,
        wake_reason=payload.wake_reason,
        next_online=payload.next_start,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
