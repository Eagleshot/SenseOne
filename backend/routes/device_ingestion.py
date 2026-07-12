"""HMAC-signed device ingestion routes."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from constants import ALLOWED_IMAGE_EXTENSIONS
from db import sqlite_repo
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

router = APIRouter(prefix="/stations", tags=["Ingest"])

# Error responses common to every signed device route, surfaced in the OpenAPI
# schema. Each route spreads this and adds the failures specific to its payload.
# Note: no 404 — an unknown station id 401s like a station without a secret, so
# unauthenticated callers can't probe which station ids exist.
_SIGNED_REQUEST_ERRORS: dict[int | str, dict[str, str]] = {
    400: {"description": "Malformed station id in the request path."},
    401: {
        "description": (
            "Missing or invalid HMAC signature: absent/blank signing headers, "
            "X-Timestamp outside the ±300 s window, a replayed X-Nonce, a "
            "signature mismatch, an unknown station id, or no device secret "
            "provisioned for the station."
        )
    },
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

    sqlite_repo.append_image(
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
        "Return the capture schedule and location a device needs for its next "
        "wake cycle (start/stop minutes, capture interval, lat/lon/alt). A device "
        "typically calls this right after syncing its clock, before capturing.\n\n"
        "Requires a valid **v1 HMAC signature** (`X-Station-Id`, `X-Timestamp`, "
        "`X-Nonce`, `X-Signature` headers); the request carries no body."
    ),
    responses=_SIGNED_REQUEST_ERRORS,
)
async def get_device_station_config(
    station_id: ValidStationId,
    request: Request,
) -> DeviceConfig:
    await verify_station_signature(station_id, request, max_body_bytes=MAX_JSON_BODY_BYTES)
    config = sqlite_repo.station_config(station_id) or AppConfig()
    return DeviceConfig(
        station_start_minute=_hhmm_to_minutes(config.station_start_time),
        station_stop_minute=_hhmm_to_minutes(config.station_stop_time),
        use_sunrise_sunset=config.use_sunrise_sunset,
        capture_interval_minutes=config.capture_interval_minutes,
        lat=config.lat,
        lon=config.lon,
        alt=config.alt,
        name=sqlite_repo.station_name_token(station_id),
    )


@router.post(
    "/{station_id}/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one image",
    description=(
        "Store one image capture for an existing station. The request body is the "
        "**raw image bytes** (not multipart); set `Content-Type` to `image/jpeg`, "
        "`image/png`, or `image/webp`. The server also sniffs the bytes and rejects "
        "anything that is not a real image of a supported type.\n\n"
        "Requires a valid **v1 HMAC signature** (`X-Station-Id`, `X-Timestamp`, "
        "`X-Nonce`, `X-Signature` headers). Uploads are capped at "
        "`APP_MAX_UPLOAD_BYTES` (default 25 MB) and refused once free disk would "
        "drop below `APP_MIN_FREE_DISK_BYTES`.\n\n"
        "Capture time and camera are read from `X-Filename`."
    ),
    responses={
        **_SIGNED_REQUEST_ERRORS,
        400: {"description": "Invalid Content-Length, empty body, or malformed station id."},
        413: {"description": "Upload exceeds APP_MAX_UPLOAD_BYTES."},
        415: {"description": "Unsupported image type, or the bytes are not a recognised image."},
        422: {
            "description": (
                "A supplied X-Filename is malformed (must match "
                "YYYYMMDD_HHMMZ_<camera>.<ext>)."
            )
        },
        507: {"description": "Server storage is full; the upload was refused."},
    },
)
async def upload_station_image(
    station_id: ValidStationId,
    request: Request,
    x_filename: str | None = Header(
        default=None,
        description=(
            "Capture filename `YYYYMMDD_HHMMZ_<camera>.<ext>` — the UTC capture "
            "minute plus a camera/stream token. Optional: when omitted or blank the "
            "server stamps a default name from the current UTC minute. When supplied "
            "it must match this format, otherwise the upload is rejected with 422."
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
    name_token = sqlite_repo.station_name_token(station_id)
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
        "Append one device check-in to a station's history. The signed JSON body is a "
        "shared envelope — optional `timestamp`, `nextStart`, and device log fields "
        "(`firmwareVersion`, `wakeReason`) — plus a `readings` array, one entry per "
        "channel. Each reading's `channel` is optional (defaults to `default`) but "
        "resolved channels must be unique; every other key in a reading is a numeric "
        "measurement, stored verbatim, so a device can report whatever it measures "
        "without a server change. `readings` may be omitted/empty for an envelope-only "
        "heartbeat. When `timestamp` is omitted the server stamps receipt time.\n\n"
        "On success returns **204 No Content** (no body). Requires a valid **v1 HMAC "
        "signature** (`X-Station-Id`, `X-Timestamp`, `X-Nonce`, `X-Signature` headers) "
        "and `Content-Type: application/json`."
    ),
    responses={
        **_SIGNED_REQUEST_ERRORS,
        413: {"description": "Request body exceeds the 1 MiB check-in cap."},
        422: {
            "description": (
                "Body failed validation: bad timestamp/nextStart, a non-numeric or "
                "out-of-range metric, too many metric fields/readings, an invalid or "
                "duplicate channel, or an unknown top-level key."
            )
        },
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": SensorReadingRequest.model_json_schema()}
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=jsonable_encoder(exc.errors()),
        ) from exc
    timestamp = payload.timestamp or iso_utc(datetime.now(timezone.utc))
    channel_metrics = [(reading.resolved_channel, reading.metrics) for reading in payload.readings]
    sqlite_repo.append_reading(
        station_id,
        timestamp,
        channel_metrics,
        firmware_version=payload.firmware_version,
        wake_reason=payload.wake_reason,
        next_online=payload.next_start,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
