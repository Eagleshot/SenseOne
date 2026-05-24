"""Station configuration management."""

import logging
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from constants import STATION_CONFIG_FILENAME, STATION_DB_FILENAME
from models import AppConfig


CONFIG_FIELDS = tuple(AppConfig.model_fields.keys())
RUNTIME_STATUS_FIELDS = ("last_online", "next_online")
EDITABLE_CONFIG_FIELDS = tuple(field for field in CONFIG_FIELDS if field not in RUNTIME_STATUS_FIELDS)

_UNSET: object = object()

META_OWNER_KEY = "_owner"
META_DEVICE_HMAC_SECRET_KEY = "_device_hmac_secret_b64"
META_FIELDS = (META_OWNER_KEY, META_DEVICE_HMAC_SECRET_KEY)


def get_data_dir() -> Path:
    """Get data directory from environment."""
    base_dir = Path(__file__).resolve().parent
    return Path(os.getenv("APP_DATA_DIR") or (base_dir / "data")).resolve()


def station_db_path(base_dir: Path, station_id: str) -> Path:
    """Get the database file path for a station."""
    return base_dir / station_id / STATION_DB_FILENAME


def _read_config_doc(base_dir: Path, station_id: str) -> dict:
    """Read the raw station config document, returning {} on any error."""
    config_path = base_dir / station_id / STATION_CONFIG_FILENAME
    if not config_path.exists():
        return {}
    try:
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logging.error("Failed to read station config for %s: %s", station_id, exc)
        return {}
    if not isinstance(parsed, dict):
        logging.error("Station config for %s is not a mapping; using defaults.", station_id)
        return {}
    return parsed


def _write_config_doc(base_dir: Path, station_id: str, document: dict) -> None:
    """Write the raw station config document."""
    station_root = base_dir / station_id
    station_root.mkdir(parents=True, exist_ok=True)
    (station_root / STATION_CONFIG_FILENAME).write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def read_station_config(base_dir: Path, station_id: str) -> AppConfig:
    """Read station configuration from file. On read or parse failure, falls back to defaults."""
    if not (base_dir / station_id / STATION_CONFIG_FILENAME).exists():
        ensure_station_dir(base_dir, station_id)

    defaults = AppConfig().model_dump()
    raw = _read_config_doc(base_dir, station_id)
    defaults.update({k: v for k, v in raw.items() if k in CONFIG_FIELDS})
    last_online, next_online = read_station_runtime_status(base_dir, station_id)
    defaults["last_online"] = last_online
    defaults["next_online"] = next_online
    try:
        return AppConfig(**defaults)
    except ValidationError as exc:
        logging.error("Station config for %s failed validation: %s", station_id, exc)
        return AppConfig()


def write_station_config(base_dir: Path, station_id: str, values: AppConfig) -> None:
    """Write station configuration to file, preserving server-managed meta fields."""
    ensure_station_dir(base_dir, station_id)
    existing = _read_config_doc(base_dir, station_id)
    payload = {field: getattr(values, field) for field in EDITABLE_CONFIG_FIELDS}
    last_online, next_online = read_station_runtime_status(base_dir, station_id)
    payload["last_online"] = last_online
    payload["next_online"] = next_online
    for meta_key in META_FIELDS:
        if meta_key in existing:
            payload[meta_key] = existing[meta_key]
    _write_config_doc(base_dir, station_id, payload)


def read_station_runtime_status(base_dir: Path, station_id: str) -> tuple[str | None, str | None]:
    """Return runtime status timestamps derived from station SQLite data."""
    from station_db import latest_status_from_db

    _, _, last_online, next_online = latest_status_from_db(station_db_path(base_dir, station_id), station_id)
    return last_online, next_online


def write_station_runtime_status(
    base_dir: Path,
    station_id: str,
    *,
    last_online: str | None,
    next_online: str | None,
) -> None:
    """Update only runtime status fields in the station config document."""
    ensure_station_dir(base_dir, station_id)
    existing = _read_config_doc(base_dir, station_id)
    if not existing:
        existing = {field: getattr(AppConfig(), field) for field in CONFIG_FIELDS}
    existing["last_online"] = last_online
    existing["next_online"] = next_online
    _write_config_doc(base_dir, station_id, existing)


def read_station_owner(base_dir: Path, station_id: str) -> str | None:
    """Return the username that owns this station, or None if unowned."""
    value = _read_config_doc(base_dir, station_id).get(META_OWNER_KEY)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def read_station_device_hmac_secret_b64(base_dir: Path, station_id: str) -> str | None:
    """Return the base64url-encoded device HMAC secret for this station, or None."""
    value = _read_config_doc(base_dir, station_id).get(META_DEVICE_HMAC_SECRET_KEY)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def write_station_meta(
    base_dir: Path,
    station_id: str,
    *,
    owner: str | None = _UNSET,
    device_hmac_secret_b64: str | None = _UNSET,
) -> None:
    """Update server-managed meta fields without touching user-editable config."""
    ensure_station_dir(base_dir, station_id)
    existing = _read_config_doc(base_dir, station_id)
    if not existing:
        existing = {field: getattr(AppConfig(), field) for field in CONFIG_FIELDS}
    if owner is not _UNSET:
        if owner is None:
            existing.pop(META_OWNER_KEY, None)
        else:
            existing[META_OWNER_KEY] = owner
    if device_hmac_secret_b64 is not _UNSET:
        if device_hmac_secret_b64 is None:
            existing.pop(META_DEVICE_HMAC_SECRET_KEY, None)
        else:
            existing[META_DEVICE_HMAC_SECRET_KEY] = device_hmac_secret_b64
    _write_config_doc(base_dir, station_id, existing)


def ensure_station_dir(base_dir: Path, station_id: str) -> None:
    """Ensure station directory and database exist."""
    from station_db import ensure_station_db

    station_root = base_dir / station_id
    (station_root / "images").mkdir(parents=True, exist_ok=True)

    config_file = station_root / STATION_CONFIG_FILENAME
    if not config_file.exists():
        defaults = AppConfig()
        config_file.write_text(
            yaml.safe_dump(
                {field: getattr(defaults, field) for field in CONFIG_FIELDS},
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    ensure_station_db(station_db_path(base_dir, station_id))
