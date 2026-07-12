"""SQLAlchemy 2.0 ORM models for the Eagleshot control plane (SQLite).

These models are the single source of truth for the schema. The Alembic
migrations under ``../migrations`` are generated from this metadata and own the
schema applied at startup (db.migrate.run_migrations); a drift guard keeps them
honest (tests/test_migrations.py). Generic SQLAlchemy types throughout so the
models map cleanly onto SQLite.

Identity note: `users.email` is the login identity (unique, required); the
`APP_AUTH_EMAIL` env var bootstraps the first admin. A user owns its stations
directly (`Station.owner_id`); there is no separate account/tenant table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base; `Base.metadata` is what the Alembic migrations are generated from."""


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    """A login that owns its stations. `is_platform_admin` is the cross-tenant superuser."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # login identity
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)  # PBKDF2
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Entitlement plan key (see entitlements.PLANS). The user is the owning entity
    # today, so limits resolve from here; if an Account layer is added later this
    # column moves with ownership.
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="free", server_default="free")
    created_at: Mapped[datetime] = _created_at()

    stations: Mapped[list[Station]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class AuthSession(Base):
    """A browser/API login session, persisted so deploys/restarts don't log users out.

    The token itself never touches the database: `token_hash` is its SHA-256 hex,
    so a leaked control DB does not leak live session tokens. Identified by the
    user's email (the login identity); a session for a since-deleted user fails
    at user resolution, exactly like the old in-memory store.
    """

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("idx_auth_sessions_expires", "expires_at"),)


class Station(Base):
    """Station metadata + schedule plus its owner (a user).

    Two external handles, each doing one job:
    - ``public_id`` — opaque, **stable**: the canonical API id, the device
      ``STATION_ID`` (HMAC path), and the image storage path. Never changes, so
      devices/links/files survive a rename.
    - ``url_slug`` — human-friendly, **editable**: the pretty public URL. Derived
      from the title and regenerated when the title changes (old URLs are not
      preserved — stable links should use ``public_id``).
    """

    __tablename__ = "stations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    public_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url_slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # metadata
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    country: Mapped[str] = mapped_column(Text, nullable=False, default="")
    country_emoji: Mapped[str] = mapped_column(Text, nullable=False, default="")
    lat: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    lon: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    alt: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # schedule
    station_start_time: Mapped[str] = mapped_column(String(5), nullable=False, default="06:00")
    station_stop_time: Mapped[str] = mapped_column(String(5), nullable=False, default="20:00")
    use_sunrise_sunset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capture_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped[User] = relationship(back_populates="stations")
    secrets: Mapped[list[StationDeviceSecret]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )
    images: Mapped[list[StationImage]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )
    readings: Mapped[list[SensorReading]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )
    datastreams: Mapped[list[Datastream]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_stations_owner", "owner_id"),)


class StationDeviceSecret(Base):
    """Per-station HMAC secret(s). Symmetric, so stored RECOVERABLY (encrypted at rest).

    Multiple rows per station support rotation WITH OVERLAP: rotating sets
    `expires_at` on the old row instead of dropping it, so a device that hasn't
    been re-flashed keeps verifying during the grace window.
    """

    __tablename__ = "station_device_secrets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    station_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), nullable=False
    )
    secret_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # encrypted base64url secret
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NULL = active

    station: Mapped[Station] = relationship(back_populates="secrets")

    __table_args__ = (Index("idx_device_secrets_station", "station_id"),)


class StationImage(Base):
    """Image metadata. The blob itself stays on disk/object storage at `storage_key`."""

    __tablename__ = "station_images"

    # INTEGER on SQLite so the PK aliases ROWID and autoincrements (a BIGINT PK
    # does not), BigInteger elsewhere.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    # Camera/stream token parsed from the filename (YYYYMMDD_HHMMZ_<stream>.ext).
    # Nullable: names that don't match just have no stream. Lets future per-camera
    # timelines filter without re-keying this table (filename already disambiguates).
    stream: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    station: Mapped[Station] = relationship(back_populates="images")

    __table_args__ = (
        Index("idx_images_station_captured", "station_id", captured_at.desc()),
        # One timeline row per (station, filename); a re-upload updates in place.
        Index("uq_images_station_filename", "station_id", "filename", unique=True),
    )


class SensorReading(Base):
    """One device check-in envelope: a timestamp plus per-message device labels.

    The numeric measurements from this check-in live in `observations`, one row
    per (metric, channel). The string/categorical device labels that are not
    measurements stay here: `firmware_version` (free-form, so custom firmware can
    report anything) and `wake_reason`.
    """

    __tablename__ = "sensor_readings"

    # INTEGER on SQLite so the PK aliases ROWID and autoincrements (see StationImage.id).
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_online: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    firmware_version: Mapped[str | None] = mapped_column(Text)
    wake_reason: Mapped[str | None] = mapped_column(Text)

    station: Mapped[Station] = relationship(back_populates="readings")
    observations: Mapped[list[Observation]] = relationship(
        back_populates="reading", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_readings_station_recorded", "station_id", recorded_at.desc()),)


class Datastream(Base):
    """One measurement channel for a station: a (metric, channel) pair.

    Identity is (station, metric, channel): a station with two temperature
    sensors (e.g. indoor/outdoor) has two datastreams that share the metric but
    differ by channel. `unit` is the canonical unit resolved from the metric
    registry when the stream is first seen (NULL for an unregistered metric), so
    stored history stays self-describing.
    """

    __tablename__ = "datastreams"

    id: Mapped[uuid.UUID] = _uuid_pk()
    station_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    unit: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()

    station: Mapped[Station] = relationship(back_populates="datastreams")
    observations: Mapped[list[Observation]] = relationship(
        back_populates="datastream", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_datastreams_station_metric_channel", "station_id", "metric", "channel", unique=True),
    )


class Observation(Base):
    """One numeric measurement: a value on a datastream at a point in time.

    `reading_id` groups the observations that arrived in the same device check-in;
    `recorded_at` is denormalised from the reading so per-datastream time queries
    don't need a join.
    """

    __tablename__ = "observations"

    # INTEGER on SQLite so the PK aliases ROWID and autoincrements (see StationImage.id).
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    datastream_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datastreams.id", ondelete="CASCADE"), nullable=False
    )
    reading_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_readings.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Double, nullable=False)
    quality_flag: Mapped[str | None] = mapped_column(Text)

    datastream: Mapped[Datastream] = relationship(back_populates="observations")
    reading: Mapped[SensorReading] = relationship(back_populates="observations")

    __table_args__ = (
        Index("idx_observations_datastream_recorded", "datastream_id", recorded_at.desc()),
        # FK index: station deletion cascades stations -> sensor_readings ->
        # observations, and SQLite looks up child rows per deleted reading.
        # Without this it full-scans observations once per reading row.
        Index("idx_observations_reading", "reading_id"),
    )
