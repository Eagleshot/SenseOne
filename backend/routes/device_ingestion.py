"""HMAC-signed device ingestion routes."""

import logging
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status

from config import camera_db_path, camera_dir, get_data_dir
from constants import ALLOWED_IMAGE_EXTENSIONS
from models import ImageUploadResponse, SensorHistoryResponse, SensorReadingRequest
from routes import ValidStationId
from station_access import require_station_exists
from station_db import append_camera_image, append_sensor_reading
from station_hmac import verify_station_signature
from utils import is_supported_image_upload, iso_utc, media_type_from_path, sanitize_filename


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


def _reject_oversize_content_length(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if not content_length:
        return
    try:
        content_length_value = int(content_length)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length header.") from exc
    if content_length_value > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload too large. Maximum is {MAX_UPLOAD_BYTES} bytes.",
        )


def store_uploaded_image(
    camera_id: str,
    filename: str,
    body: bytes,
    content_type: str | None,
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
    require_station_exists(camera_id)

    images_dir = camera_dir(data_dir, camera_id) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{int(time.time() * 1000)}-{filename}"
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

    captured_at = datetime.now(timezone.utc).isoformat()
    append_camera_image(
        camera_db_path(data_dir, camera_id),
        filename=stored_filename,
        content_type=detected_media_type,
        size_bytes=len(body),
        captured_at=captured_at,
    )
    return stored_filename, f"/stations/{camera_id}/images/{stored_filename}"


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
) -> ImageUploadResponse:
    _reject_oversize_content_length(request)
    body = await verify_station_signature(station_id, request)
    stored_filename, image_url = store_uploaded_image(
        camera_id=station_id,
        filename=sanitize_filename(x_filename or "default.jpg"),
        body=body,
        content_type=request.headers.get("content-type"),
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
    append_sensor_reading(
        camera_db_path(get_data_dir(), station_id),
        timestamp=timestamp,
        **payload.model_dump(exclude={"timestamp"}),
    )
    return SensorHistoryResponse(timestamp=timestamp, **payload.model_dump(exclude={"timestamp"}))
