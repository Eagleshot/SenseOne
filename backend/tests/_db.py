"""SQLite test harness helpers.

Tests run against a throwaway SQLite file (TEST_DATABASE_URL, defaulting to a temp
file) — no database server required. Schema is built from the ORM metadata once
per session, and each test starts from a fresh, empty database.
"""

import os
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or (
    f"sqlite:///{(Path(tempfile.gettempdir()) / 'eagleshot_test.db').as_posix()}"
)


def stamp_head() -> None:
    """Mark the test DB as up-to-date so create_app()'s startup upgrade is a no-op.

    Tests build the schema from ORM metadata (fast) rather than by running the
    migrations. The app, however, runs `alembic upgrade head` at startup
    (db.migrate.run_migrations); stamping alembic_version to head here stops that
    upgrade from trying to recreate the already-present tables.
    """
    from alembic import command

    from db.migrate import _alembic_config

    command.stamp(_alembic_config(), "head")


def init_engine():
    """Point the app engine at the test DB and (re)create the schema."""
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    import db.session as session_module

    session_module._engine = None
    session_module._sessionmaker = None
    from db.models import Base
    from db.session import get_engine

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    stamp_head()
    return engine


def reset_data() -> None:
    """Drop and recreate every table for a clean per-test database."""
    from db.models import Base
    from db.session import get_engine

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def create_owner(email: str, password: str = "devpassword123", *, is_admin: bool = False):
    """Create a user via the app layer; returns the users.User (has owner_id)."""
    from users import create_user

    return create_user(email, password, is_admin=is_admin)


def _default_owner_id(session) -> uuid.UUID:
    from db.models import User

    user = session.scalar(select(User).where(User.email == "test-default-owner@example.com"))
    if user is None:
        user = User(email="test-default-owner@example.com", password_hash="x")
        session.add(user)
        session.flush()
    return user.id


def create_station_row(public_id: str, *, is_public: bool = True, owner_id: str | None = None,
                       url_slug: str | None = None, **fields) -> str:
    """Insert a station row keyed by an explicit public_id (deterministic for tests).

    url_slug defaults to the public_id. Uses a shared default owner unless
    owner_id is given. Returns the public_id (what API paths use).
    """
    from db.models import Station
    from db.session import session_scope

    with session_scope() as session:
        owner = uuid.UUID(owner_id) if owner_id else _default_owner_id(session)
        session.add(Station(
            public_id=public_id,
            url_slug=url_slug or public_id,
            owner_id=owner,
            is_public=is_public,
            title=fields.pop("title", "Test Station"),
            **fields,
        ))
    return public_id


def set_station_public(public_id: str, is_public: bool) -> None:
    from db.models import Station
    from db.session import session_scope

    with session_scope() as session:
        session.scalar(select(Station).where(Station.public_id == public_id)).is_public = is_public


def add_reading(public_id: str, recorded_at, metrics: dict, next_online=None) -> None:
    """Persist a reading via the real repo path (envelope + observations).

    ``metrics`` may include the reserved device labels (firmwareVersion /
    wakeReason); they are split out the same way the device route does, leaving
    the numeric measurements to become observations.
    """
    from db import sqlite_repo
    from utils import iso_utc

    data = dict(metrics or {})
    firmware_version = data.pop("firmwareVersion", None)
    wake_reason = data.pop("wakeReason", None)
    timestamp = recorded_at if isinstance(recorded_at, str) else iso_utc(recorded_at)
    next_online_iso = next_online if (next_online is None or isinstance(next_online, str)) else iso_utc(next_online)
    sqlite_repo.append_reading(
        public_id,
        timestamp,
        data,
        firmware_version=firmware_version,
        wake_reason=wake_reason,
        next_online=next_online_iso,
    )


def add_image(public_id: str, filename: str, captured_at, *, content_type="image/jpeg", size_bytes=1000) -> None:
    from db.models import Station, StationImage
    from db.session import session_scope
    from utils import parse_iso_timestamp

    with session_scope() as session:
        station = session.scalar(select(Station).where(Station.public_id == public_id))
        session.add(StationImage(
            station_id=station.id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            captured_at=parse_iso_timestamp(captured_at) if isinstance(captured_at, str) else captured_at,
            storage_key=f"{public_id}/images/{filename}",
        ))


def station_owner_id(public_id: str) -> str | None:
    from db import sqlite_repo

    return sqlite_repo.station_owner_id(public_id)


def _iso(value):
    from utils import iso_utc

    return iso_utc(value) if value is not None else None


def latest_image(public_id: str) -> dict | None:
    from db.models import Station, StationImage
    from db.session import session_scope

    with session_scope() as session:
        station = session.scalar(select(Station).where(Station.public_id == public_id))
        img = session.scalar(
            select(StationImage).where(StationImage.station_id == station.id)
            .order_by(StationImage.id.desc()).limit(1)
        )
        if img is None:
            return None
        return {
            "filename": img.filename,
            "content_type": img.content_type,
            "size_bytes": img.size_bytes,
            "captured_at": _iso(img.captured_at),
            "next_online": _iso(img.next_online),
        }


def latest_reading(public_id: str) -> dict | None:
    from db.models import Datastream, Observation, SensorReading, Station
    from db.session import session_scope

    with session_scope() as session:
        station = session.scalar(select(Station).where(Station.public_id == public_id))
        row = session.scalar(
            select(SensorReading).where(SensorReading.station_id == station.id)
            .order_by(SensorReading.id.desc()).limit(1)
        )
        if row is None:
            return None
        observations = session.execute(
            select(Datastream.metric, Observation.value)
            .join(Datastream, Observation.datastream_id == Datastream.id)
            .where(Observation.reading_id == row.id)
        ).all()
        return {
            "recorded_at": _iso(row.recorded_at),
            "next_online": _iso(row.next_online),
            "firmware_version": row.firmware_version,
            "wake_reason": row.wake_reason,
            "metrics": {metric: value for metric, value in observations},
        }
