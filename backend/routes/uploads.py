"""File upload routes."""

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from auth import get_current_username
from config import camera_db_path, camera_dir, ensure_camera_dir, get_data_dir
from constants import ALLOWED_IMAGE_EXTENSIONS
from utils import (
    is_supported_image_upload,
    media_type_from_path,
    sanitize_camera_id,
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

router = APIRouter(tags=["Uploads"])


def _require_existing_camera(data_dir, camera_id: str) -> None:
    """Reject uploads for camera ids that don't already exist."""
    if not camera_dir(data_dir, camera_id).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown station id.",
        )


async def store_uploaded_image(
    camera_id: str,
    filename: str,
    request: Request,
    content_type: str | None,
    *,
    auto_create: bool,
) -> tuple[str, str]:
    """Store an uploaded image file."""
    if not is_supported_image_upload(filename, content_type):
        supported = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type. Allowed extensions: {supported}",
        )

    data_dir = get_data_dir()
    if auto_create:
        ensure_camera_dir(data_dir, camera_id)
    else:
        _require_existing_camera(data_dir, camera_id)

    camera_root = camera_dir(data_dir, camera_id)
    images_dir = camera_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    timestamp_ms = int(time.time() * 1000)
    stored_filename = f"{timestamp_ms}-{filename}"
    file_path = images_dir / stored_filename
    size_bytes = 0

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_value = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            ) from exc
        if content_length_value > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload too large. Maximum is {MAX_UPLOAD_BYTES} bytes.",
            )

    try:
        with file_path.open("wb") as target:
            async for chunk in request.stream():
                if not chunk:
                    continue
                size_bytes += len(chunk)
                if size_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload too large. Maximum is {MAX_UPLOAD_BYTES} bytes.",
                    )
                target.write(chunk)

        if size_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty upload.",
            )

        # Validate the saved bytes are actually an image, not just a matching extension.
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

    db_path = camera_db_path(data_dir, camera_id)
    captured_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO camera_images (filename, content_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (stored_filename, detected_media_type, size_bytes, captured_at),
        )
        connection.commit()

    return stored_filename, f"/stations/{camera_id}/images/{stored_filename}"


@router.post(
    "/upload",
    response_class=PlainTextResponse,
    summary="Upload Image By Header",
    description="Upload an image by providing the target station ID in the X-Camera-Id header or webcam_id query parameter.",
)
async def upload_image(
    request: Request,
    x_camera_id: Optional[str] = Header(default=None, alias="X-Camera-Id"),
    webcam_id: Optional[str] = Query(default=None),
    x_filename: Optional[str] = Header(default=None),
    _: str = Depends(get_current_username),
) -> PlainTextResponse:
    """Upload an image for a station. Auto-creates the station directory if needed."""
    if not x_camera_id and not webcam_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="camera id is required via X-Camera-Id header or webcam_id query parameter",
        )
    camera_id = sanitize_camera_id(x_camera_id or webcam_id)
    filename = sanitize_filename(x_filename or "default.jpg")
    stored_filename, _ = await store_uploaded_image(
        camera_id=camera_id,
        filename=filename,
        request=request,
        content_type=request.headers.get("content-type"),
        auto_create=True,
    )
    logging.info("File saved for camera %s as %s", camera_id, stored_filename)
    return PlainTextResponse(f"File uploaded as {stored_filename}")


@router.post(
    "/upload/{camera_id}",
    response_class=PlainTextResponse,
    summary="Upload Image By Path",
    description="Upload an image to an existing station identified in the request path.",
)
async def upload_image_for_camera(
    request: Request,
    camera_id: str,
    x_filename: Optional[str] = Header(default=None),
    _: str = Depends(get_current_username),
) -> PlainTextResponse:
    """Upload an image for a specific existing station."""
    target_camera_id = sanitize_camera_id(camera_id)
    filename = sanitize_filename(x_filename or "default.jpg")
    stored_filename, _ = await store_uploaded_image(
        camera_id=target_camera_id,
        filename=filename,
        request=request,
        content_type=request.headers.get("content-type"),
        auto_create=False,
    )
    logging.info("File saved for camera %s as %s", target_camera_id, stored_filename)
    return PlainTextResponse(f"File uploaded as {stored_filename}")
