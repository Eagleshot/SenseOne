"""Backend data facade used by the route handlers.

Control-plane data lives in a SQLite control-plane DB (db.sqlite_repo). Image blobs
are stored on disk under APP_DATA_DIR at "<public_id>/images/<filename>", and
replay nonces live in a separate standalone sqlite store. This module is a thin,
stable surface the routes import; it delegates to db.sqlite_repo.
"""

from __future__ import annotations

from db import sqlite_repo
from metrics_registry import DEFAULT_CHANNEL
from models import AppConfig
from station_db import StationStatus


def list_station_views(user) -> list[tuple[str, str, AppConfig, StationStatus, bool]]:
    """(public_id, url_slug, config, status, can_edit) for every viewable station, access-filtered."""
    return sqlite_repo.list_station_views(user)


def create_station(payload, user) -> str:
    """Create a station owned by `user`; returns the new opaque public_id."""
    return sqlite_repo.create_station(payload, user.owner_id)


def station_view(public_id: str) -> tuple[str, AppConfig, StationStatus] | None:
    """(url_slug, config, status) for one station, or None if unknown."""
    return sqlite_repo.station_view(public_id)


def station_config(slug: str) -> AppConfig:
    return sqlite_repo.station_config(slug) or AppConfig()


def save_station_config(slug: str, config: AppConfig) -> None:
    sqlite_repo.save_station_config(slug, config)


def latest_status(slug: str) -> StationStatus:
    return sqlite_repo.latest_status(slug)


def image_captures(slug: str, count: int) -> list[dict[str, str]]:
    return sqlite_repo.image_captures(slug, count)


def sensor_readings(slug: str, hours: int) -> list[dict[str, object]]:
    return sqlite_repo.sensor_readings(slug, hours)


def append_image(slug: str, *, filename, content_type, size_bytes, captured_at, next_online=None) -> None:
    sqlite_repo.append_image(
        slug, filename=filename, content_type=content_type, size_bytes=size_bytes,
        captured_at=captured_at, next_online=next_online,
    )


def append_reading(
    slug: str,
    timestamp,
    metrics,
    *,
    channel=DEFAULT_CHANNEL,
    firmware_version=None,
    wake_reason=None,
    next_online=None,
) -> None:
    sqlite_repo.append_reading(
        slug,
        timestamp,
        metrics,
        channel=channel,
        firmware_version=firmware_version,
        wake_reason=wake_reason,
        next_online=next_online,
    )


def read_device_secret_b64(slug: str) -> str | None:
    return sqlite_repo.read_device_secret_b64(slug)
