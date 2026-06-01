"""HMAC-signed device ingestion routes."""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status

from config import get_data_dir, read_station_config, station_db_path
from constants import ALLOWED_IMAGE_EXTENSIONS
from models import AppConfig, ImageUploadResponse, SensorHistoryResponse, SensorReadingRequest
from routes import ValidStationId
from station_access import require_station_exists
from station_db import append_sensor_reading, append_station_image
from station_hmac import verify_station_signature
from utils import (
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


MAX_UPLOAD_BYTES = _parse_max_upload_bytes()

router = APIRouter(prefix="/stations", tags=["Device"])


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

    append_station_image(
        station_db_path(data_dir, station_id),
        filename=stored_filename,
        content_type=detected_media_type,
        size_bytes=len(body),
        captured_at=iso_utc(image_timestamp),
        next_online=next_online,
    )
    return stored_filename, f"/stations/{station_id}/images/{stored_filename}"


@router.get(
    "/{station_id}/config",
    response_model=AppConfig,
    summary="Get station config for a device",
    description="Return the station config to a device after validating its HMAC signature.",
)
async def get_device_station_config(
    station_id: ValidStationId,
    request: Request,
) -> AppConfig:
    await verify_station_signature(station_id, request)
    return read_station_config(get_data_dir(), station_id)


@router.post(
    "/{station_id}/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one image",
    description="Store one signed JPEG/PNG/WebP image capture for an existing station.",
)
async def upload_station_image(
    station_id: ValidStationId,
    request: Request,
    x_filename: str | None = Header(default=None, description="Optional filename suggestion."),
    x_next_online: str | None = Header(default=None, description="Optional ISO 8601 next check-in timestamp."),
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
    stored_filename, image_url = store_uploaded_image(
        station_id=station_id,
        filename=sanitize_filename(x_filename or "default.jpg"),
        body=body,
        content_type=request.headers.get("content-type"),
        next_online=parse_next_online(x_next_online),
    )
    logging.info("File saved for station %s as %s", station_id, stored_filename)
    return ImageUploadResponse(filename=stored_filename, url=image_url)


@router.post(
    "/{station_id}/sensor-readings",
    response_model=SensorHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one sensor reading",
    description="Append one signed sensor reading to a station's history.",
)
async def create_sensor_reading(
    station_id: ValidStationId,
    payload: SensorReadingRequest,
    request: Request,
) -> SensorHistoryResponse:
    await verify_station_signature(station_id, request)
    timestamp = payload.timestamp or iso_utc(datetime.now(timezone.utc))
    metrics = payload.metrics
    next_online = payload.next_start
    data_dir = get_data_dir()
    append_sensor_reading(
        station_db_path(data_dir, station_id),
        timestamp,
        metrics,
        next_online=next_online,
    )
    return SensorHistoryResponse(timestamp=timestamp, **metrics)
