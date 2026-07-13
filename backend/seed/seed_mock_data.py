"""Seed demo data into the SQLite control plane.

Inserts users / stations / sensor_readings / station_images rows and writes the
timeline image blobs to disk (``storage_key`` = ``"<public_id>/images/<filename>"``).

The script brings the schema up to head itself (via db.migrate.run_migrations,
the same path the app uses at startup), so no separate setup is needed. By default
it writes the same SQLite file the app uses (``<APP_DATA_DIR>/control.db``).

Run from `backend/`:
    python seed/seed_mock_data.py --overwrite
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from security import hash_secret  # noqa: E402
from db.migrate import run_migrations  # noqa: E402
from db.models import Datastream, Observation, SensorReading, Station, StationImage, User  # noqa: E402
from db.sqlite_repo import new_public_id, resolve_datastream  # noqa: E402
from db.session import get_engine  # noqa: E402
from metrics_registry import DEFAULT_CHANNEL  # noqa: E402
from settings import get_data_dir  # noqa: E402
from utils import parse_iso_timestamp, sanitize_station_id, station_name_token  # noqa: E402

try:
    from .mock_data import (
        DEFAULT_OWNER_PASSWORD,
        SAMPLE_IMAGE_FILES,
        SAMPLE_PNG_BYTES,
        SENSOR_HISTORY_HOURS,
        WEBCAM_SEED,
        ensure_seed_images,
        generate_historical_data,
    )
except ImportError:  # run as a script rather than a package module
    from mock_data import (
        DEFAULT_OWNER_PASSWORD,
        SAMPLE_IMAGE_FILES,
        SAMPLE_PNG_BYTES,
        SENSOR_HISTORY_HOURS,
        WEBCAM_SEED,
        ensure_seed_images,
        generate_historical_data,
    )

DEMO_OWNER_EMAIL = "demo@example.com"  # owns any station without an explicit owner

# Demo camera streams: timeline captures alternate between these so seeded stations
# exercise the per-camera `stream` field (parsed from the capture-format filename).
SEED_CAMERA_STREAMS = ("main", "thermal")


def _slug(value: str) -> str:
    return sanitize_station_id(value, default="station")


def _ensure_owner(session: Session, owner_email: str, password: str) -> User:
    """Ensure an owner user exists; never resets an existing password."""
    user = session.scalar(select(User).where(User.email == owner_email))
    if user is None:
        user = User(email=owner_email, password_hash=hash_secret(password))
        session.add(user)
        session.flush()  # assign user.id
        print(f"Created owner {owner_email!r} (password: {password!r}).")
    return user


def _upsert_station(session: Session, seed: dict, owner: User, overwrite: bool) -> Station:
    url_slug = _slug(str(seed["id"]))
    coords = seed.get("coordinates") or {}
    fields = dict(
        owner_id=owner.id,
        title=str(seed.get("name") or ""),
        description=str(seed.get("description") or ""),
        location=str(seed.get("location") or ""),
        country=str(seed.get("country") or ""),
        country_emoji=str(seed.get("countryEmoji") or ""),
        lat=float(coords.get("lat", 0.0)),
        lon=float(coords.get("lng", 0.0)),
        alt=float(coords.get("altitude", 0.0)),
        is_public=bool(seed.get("is_public", True)),
    )
    station = session.scalar(select(Station).where(Station.url_slug == url_slug))
    if station is None:
        station = Station(public_id=new_public_id(session), url_slug=url_slug, **fields)
        session.add(station)
        session.flush()
    elif overwrite:
        for key, value in fields.items():
            setattr(station, key, value)
    return station


def _seed_readings(session: Session, station: Station, seed: dict, overwrite: bool) -> None:
    existing = session.scalar(
        select(func.count()).select_from(SensorReading).where(SensorReading.station_id == station.id)
    )
    if existing and not overwrite:
        return
    if overwrite:
        # Deleting readings cascades their observations (FK ON DELETE CASCADE);
        # clear datastreams too so a re-seed with a changed metric set leaves none orphaned.
        session.execute(delete(SensorReading).where(SensorReading.station_id == station.id))
        session.execute(delete(Datastream).where(Datastream.station_id == station.id))

    now = datetime.now(timezone.utc)
    # Honor the seed's declared status: anchor the generated timeline so its newest
    # reading lands on `lastUpdateMinutesAgo`, and only give the station a future
    # next_online (i.e. render it online) when the seed says isOnline.
    last_seen = now - timedelta(minutes=int(seed.get("lastUpdateMinutesAgo") or 0))
    shift = last_seen - now
    next_online = None
    if seed.get("isOnline", True) and seed.get("nextUpdateMinutesIn") is not None:
        next_online = now + timedelta(minutes=int(seed["nextUpdateMinutesIn"]))

    rows = generate_historical_data(SENSOR_HISTORY_HOURS, station_id=station.url_slug)
    datastreams: dict[str, Datastream] = {}
    for index, row in enumerate(rows):
        measurements = {k: v for k, v in row.items() if k != "timestamp"}
        firmware_version = measurements.pop("firmwareVersion", None)
        wake_reason = measurements.pop("wakeReason", None)
        recorded_at = parse_iso_timestamp(row["timestamp"]) + shift
        reading = SensorReading(
            station_id=station.id,
            recorded_at=recorded_at,
            firmware_version=firmware_version,
            wake_reason=wake_reason,
            next_online=next_online if index == len(rows) - 1 else None,
        )
        session.add(reading)
        session.flush()  # assign reading.id for the observation FK
        for metric, value in measurements.items():
            if value is None:
                continue
            datastream = datastreams.get(metric)
            if datastream is None:
                datastream = resolve_datastream(session, station.id, metric, DEFAULT_CHANNEL)
                datastreams[metric] = datastream
            session.add(
                Observation(
                    datastream_id=datastream.id,
                    reading_id=reading.id,
                    recorded_at=recorded_at,
                    value=float(value),
                )
            )


def _seed_images(
    session: Session, station: Station, seed: dict, count: int, overwrite: bool, data_dir: Path
) -> None:
    if count <= 0:
        return
    existing = session.scalar(
        select(func.count()).select_from(StationImage).where(StationImage.station_id == station.id)
    )
    if existing and not overwrite:
        return
    if overwrite:
        session.execute(delete(StationImage).where(StationImage.station_id == station.id))

    images_dir = data_dir / station.public_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    ensure_seed_images(images_dir, overwrite)

    # Anchor the timeline to the seed's declared "last update" time so the newest
    # image isn't newer than the newest reading (which would override last_online).
    last_seen = datetime.now(timezone.utc) - timedelta(minutes=int(seed.get("lastUpdateMinutesAgo") or 0))
    # Frozen, filename-safe station name token — the same token the upload path bakes
    # into stored filenames, so seeded data matches real captures.
    name_token = station_name_token(
        station.title, url_slug=station.url_slug, public_id=station.public_id
    )
    for index in range(count):
        captured_at = last_seen - timedelta(minutes=(count - index) * 30)
        # Alternate cameras so each station has more than one stream.
        stream = SEED_CAMERA_STREAMS[index % len(SEED_CAMERA_STREAMS)]
        source_name = SAMPLE_IMAGE_FILES[index % len(SAMPLE_IMAGE_FILES)]
        # Device capture-format name (YYYYMMDD_HHMMZ_<name>_<stream>) so `stream`
        # parses from it the same way a real device upload would.
        filename = f"{captured_at:%Y%m%d_%H%MZ}_{name_token}_{stream}.png"
        destination = images_dir / filename
        if not destination.exists() or overwrite:
            source_file = images_dir / source_name
            destination.write_bytes(
                source_file.read_bytes() if source_file.exists() else SAMPLE_PNG_BYTES
            )
        session.add(
            StationImage(
                station_id=station.id,
                filename=filename,
                stream=stream,
                content_type="image/png",
                size_bytes=destination.stat().st_size,
                captured_at=captured_at,
                storage_key=f"{station.public_id}/images/{filename}",
            )
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo data into the SQLite control plane.")
    parser.add_argument("--database-url", help="Override DATABASE_URL for this run.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Where image blobs are written (default: the app's APP_DATA_DIR).",
    )
    parser.add_argument("--count", type=int, default=16, help="Timeline images per station (default: 16).")
    parser.add_argument("--overwrite", action="store_true", help="Clear and regenerate readings + images.")
    parser.add_argument("--station-id", action="append", default=[], help="Seed only these station ids (repeatable).")
    parser.add_argument(
        "--owner-password",
        default=DEFAULT_OWNER_PASSWORD,
        help=f"Password for newly-created owner accounts (default: {DEFAULT_OWNER_PASSWORD!r}).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    # Default the blob dir to the app's data dir so seeded image rows resolve to
    # blobs the app actually serves (both follow APP_DATA_DIR). Resolved after the
    # DATABASE_URL override so settings are read once, consistently.
    data_dir = (args.data_dir or get_data_dir()).resolve()
    run_migrations()  # build/upgrade the schema to head, stamped like the app
    engine = get_engine()

    requested = {_slug(s) for s in args.station_id}
    seeds = [s for s in WEBCAM_SEED if not requested or _slug(str(s["id"])) in requested]
    if not seeds:
        raise SystemExit("No matching stations in WEBCAM_SEED.")

    with Session(engine) as session:
        for seed in seeds:
            owner_email = str(seed.get("owner") or "").strip() or DEMO_OWNER_EMAIL
            owner = _ensure_owner(session, owner_email, args.owner_password)
            station = _upsert_station(session, seed, owner, args.overwrite)
            _seed_readings(session, station, seed, args.overwrite)
            _seed_images(session, station, seed, args.count, args.overwrite, data_dir)

        session.commit()

    print(f"Seeded {len(seeds)} stations into the SQLite control plane; image blobs under {data_dir}")


if __name__ == "__main__":
    main()
