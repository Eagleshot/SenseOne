"""HMAC-signed device ingestion routes."""

import logging
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status

import store
from config import get_data_dir
from constants import ALLOWED_IMAGE_EXTENSIONS
from models import DeviceConfig, ImageUploadResponse, SensorReadingAck, SensorReadingRequest
from routes import ValidStationId
from station_access import require_station_exists
from station_hmac import verify_station_signature
from utils import (
    default_capture_filename,
    image_timestamp_from_filename,
    is_supported_image_upload,
    iso_utc,
    media_type_from_path,
    parse_iso_timestamp,
    sanitize_filename,
)


def _parse_max_upload_bytes() -> int:
    raw_value = os.getenv("APP_MAX_UPLOAD_BYTES")
    try:
        max_bytes = int(raw_value) if raw_value else 25 * 1024 * 1024
    except ValueError as exc:
        raise RuntimeError("APP_MAX_UPLOAD_BYTES must be an integer.") from exc
    if max_bytes <= 0:
        raise RuntimeError("APP_MAX_UPLOAD_BYTES must be greater than 0.")
    return max_bytes


def _parse_min_free_disk_bytes() -> int:
    """Free-space floor below which the server stops accepting image uploads.

    A device with a valid secret (or a buggy one) can otherwise loop uploads and
    fill the disk, which takes the whole service down and can corrupt in-flight
    SQLite writes. This is a safety valve, not per-plan retention — that lands
    with the SaaS quota work. Set to 0 to disable. Default 500 MiB.
    """
    raw_value = os.getenv("APP_MIN_FREE_DISK_BYTES")
    try:
        min_bytes = int(raw_value) if raw_value else 500 * 1024 * 1024
    except ValueError as exc:
        raise RuntimeError("APP_MIN_FREE_DISK_BYTES must be an integer.") from exc
    if min_bytes < 0:
        raise RuntimeError("APP_MIN_FREE_DISK_BYTES must not be negative.")
    return min_bytes


MAX_UPLOAD_BYTES = _parse_max_upload_bytes()
MIN_FREE_DISK_BYTES = _parse_min_free_disk_bytes()


def _enforce_free_disk(data_dir, incoming_bytes: int) -> None:
    """Reject uploads with 507 when storing this body would breach the floor."""
    if MIN_FREE_DISK_BYTES <= 0:
        return
    try:
        free = shutil.disk_usage(data_dir).free
    except OSError as exc:
        logging.warning("Could not check free disk space at %s: %s", data_dir, exc)
        return
    if free - incoming_bytes < MIN_FREE_DISK_BYTES:
        logging.error(
            "Refusing upload: free disk %d would drop below floor %d after %d bytes.",
            free, MIN_FREE_DISK_BYTES, incoming_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Server storage is full. Upload rejected.",
        )

router = APIRouter(prefix="/stations", tags=["Ingest"])

# Error responses common to every signed device route, surfaced in the OpenAPI
# schema. Each route spreads this and adds the failures specific to its payload.
_SIGNED_REQUEST_ERRORS: dict[int | str, dict[str, str]] = {
    400: {"description": "Malformed station id in the request path."},
    401: {
        "description": (
            "Missing or invalid HMAC signature: absent/blank signing headers, "
            "X-Timestamp outside the ±300 s window, a replayed X-Nonce, a "
            "signature mismatch, or no device secret provisioned for the station."
        )
    },
    404: {"description": "No station exists with this id."},
}


def parse_next_online(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    parsed = parse_iso_timestamp(value)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Next-Online must be an ISO 8601 timestamp.",
        )
    return iso_utc(parsed)


def store_uploaded_image(
    station_id: str,
    filename: str,
    body: bytes,
    content_type: str | None,
    next_online: str | None = None,
) -> tuple[str, str]:
    """Persist an uploaded image that has already passed HMAC verification."""
    if not is_supported_image_upload(filename, content_type):
        supported = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type. Allowed extensions: {supported}",
        )
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload too large. Maximum is {MAX_UPLOAD_BYTES} bytes.",
        )

    data_dir = get_data_dir()
    require_station_exists(station_id)
    _enforce_free_disk(data_dir, len(body))

    images_dir = data_dir / station_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_timestamp = image_timestamp_from_filename(filename)
    if image_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Filename must match YYYYMMDD_HHMMZ_<camera>.jpg.",
        )

    stored_filename = filename
    file_path = images_dir / stored_filename

    try:
        file_path.write_bytes(body)
        detected_media_type = media_type_from_path(file_path)
        if detected_media_type is None:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File contents are not a recognised image.",
            )
    except HTTPException:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise

    store.append_image(
        station_id,
        filename=stored_filename,
        content_type=detected_media_type,
        size_bytes=len(body),
        captured_at=iso_utc(image_timestamp),
        next_online=next_online,
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
    await verify_station_signature(station_id, request)
    config = store.station_config(station_id)
    return DeviceConfig(
        station_start_minute=_hhmm_to_minutes(config.station_start_time),
        station_stop_minute=_hhmm_to_minutes(config.station_stop_time),
        use_sunrise_sunset=config.use_sunrise_sunset,
        capture_interval_minutes=config.capture_interval_minutes,
        lat=config.lat,
        lon=config.lon,
        alt=config.alt,
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
        "Capture time and camera are read from `X-Filename`; `X-Next-Online` records "
        "when the device expects to check in next, which drives the station's "
        "online/offline status."
    ),
    responses={
        **_SIGNED_REQUEST_ERRORS,
        400: {"description": "Invalid Content-Length, empty body, or malformed station id."},
        413: {"description": "Upload exceeds APP_MAX_UPLOAD_BYTES."},
        415: {"description": "Unsupported image type, or the bytes are not a recognised image."},
        422: {
            "description": (
                "A supplied X-Filename or X-Next-Online is malformed (X-Filename must "
                "match YYYYMMDD_HHMMZ_<camera>.<ext>; X-Next-Online must be ISO 8601)."
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
    x_next_online: str | None = Header(
        default=None,
        description=(
            "Optional ISO 8601 timestamp for when the device next expects to check "
            "in. Stored with the capture and used to show the station as online "
            "until this time (plus a short grace buffer) has passed."
        ),
    ),
) -> ImageUploadResponse:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_value = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length header.") from exc
        if content_length_value > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload too large. Maximum is {MAX_UPLOAD_BYTES} bytes.",
            )

    body = await verify_station_signature(station_id, request)
    content_type = request.headers.get("content-type")
    # X-Filename is optional: a device may omit it (or send blank), and the server
    # stamps a default capture name from the current UTC minute. A supplied name
    # must still match the capture format (store_uploaded_image enforces it).
    provided_name = (x_filename or "").strip()
    filename = (
        sanitize_filename(provided_name)
        if provided_name
        else default_capture_filename(content_type)
    )
    stored_filename, image_url = store_uploaded_image(
        station_id=station_id,
        filename=filename,
        body=body,
        content_type=content_type,
        next_online=parse_next_online(x_next_online),
    )
    logging.info("File saved for station %s as %s", station_id, stored_filename)
    return ImageUploadResponse(filename=stored_filename, url=image_url)


@router.post(
    "/{station_id}/sensor-readings",
    response_model=SensorReadingAck,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one sensor reading",
    description=(
        "Append one sensor reading to a station's history. The signed JSON body "
        "carries optional `timestamp`, `channel`, `nextStart`, and device log fields "
        "(`firmwareVersion`, `wakeReason`, …); any extra numeric keys are stored "
        "verbatim as metrics, so a device can report whatever it measures without a "
        "server change. When `timestamp` is omitted the server stamps receipt time.\n\n"
        "Requires a valid **v1 HMAC signature** (`X-Station-Id`, `X-Timestamp`, "
        "`X-Nonce`, `X-Signature` headers) and `Content-Type: application/json`."
    ),
    responses={
        **_SIGNED_REQUEST_ERRORS,
        422: {
            "description": (
                "Body failed validation: bad timestamp/nextStart, a non-numeric or "
                "out-of-range metric, too many metric fields, or an invalid channel."
            )
        },
    },
)
async def create_sensor_reading(
    station_id: ValidStationId,
    payload: SensorReadingRequest,
    request: Request,
) -> SensorReadingAck:
    await verify_station_signature(station_id, request)
    timestamp = payload.timestamp or iso_utc(datetime.now(timezone.utc))
    metrics = payload.metrics
    channel = payload.resolved_channel
    store.append_reading(
        station_id,
        timestamp,
        metrics,
        channel=channel,
        firmware_version=payload.firmware_version,
        wake_reason=payload.wake_reason,
        next_online=payload.next_start,
    )
    return SensorReadingAck(
        timestamp=timestamp,
        channel=channel,
        metrics={key: float(value) for key, value in metrics.items()},
        firmware_version=payload.firmware_version,
        wake_reason=payload.wake_reason,
    )
