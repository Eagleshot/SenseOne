"""SQLite implementation of the data/access/user operations.

The repository the service layer calls through `store.py`, `station_access.py`,
`users.py` and `station_hmac.py`. Synchronous so it slots into the sync route
handlers via FastAPI's threadpool.

Stations have two external handles (see db.models.Station):
- ``public_id`` — opaque, stable: the canonical API id, device ``STATION_ID``
  (HMAC path), and image storage path. Every data/device op here keys on it.
- ``url_slug`` — editable pretty URL; regenerated from the title on rename.

Image blobs and replay nonces are NOT here — blobs live on disk at
``<public_id>/images/<filename>`` and replay nonces live in a standalone sqlite store.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import aliased

from auth import hash_secret, verify_secret
from db.models import Datastream, Observation, SensorReading, Station, StationDeviceSecret, StationImage, User
from db.session import session_scope
from metrics_registry import DEFAULT_CHANNEL, metric_unit
from models import AppConfig
from station_db import StationStatus, _coerce_battery
from utils import iso_utc, parse_iso_timestamp, sanitize_station_id, stream_from_filename

# Config columns persisted on the stations row (runtime status is derived).
_CONFIG_COLUMNS = (
    "title", "description", "location", "country", "country_emoji",
    "lat", "lon", "alt", "is_public",
    "station_start_time", "station_stop_time", "use_sunrise_sunset", "capture_interval_minutes",
)


# ----- helpers ---------------------------------------------------------------

def _station(session, public_id: str) -> Station | None:
    return session.scalar(select(Station).where(Station.public_id == public_id))


def _new_public_id(session) -> str:
    """A fresh opaque, URL-safe, stable station id (12 hex chars)."""
    while True:
        candidate = secrets.token_hex(6)
        if session.scalar(select(Station.id).where(Station.public_id == candidate)) is None:
            return candidate


def _unique_url_slug(session, title: str, exclude_id: uuid.UUID | None = None) -> str:
    """Pretty URL slug from the title, unique across stations (excluding self)."""
    base = sanitize_station_id(title, default="station")

    def taken(slug: str) -> bool:
        stmt = select(Station.id).where(Station.url_slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Station.id != exclude_id)
        return session.scalar(stmt) is not None

    if not taken(base):
        return base
    for index in range(2, 100000):
        candidate = sanitize_station_id(f"{base}-{index}", default="station")
        if not taken(candidate):
            return candidate
    return f"{base}-{secrets.token_hex(3)}"


def _config_from_row(row: Station, status: StationStatus) -> AppConfig:
    return AppConfig(
        title=row.title,
        description=row.description,
        location=row.location,
        country=row.country,
        country_emoji=row.country_emoji,
        lat=row.lat,
        lon=row.lon,
        alt=row.alt,
        is_public=row.is_public,
        station_start_time=row.station_start_time,
        station_stop_time=row.station_stop_time,
        use_sunrise_sunset=row.use_sunrise_sunset,
        capture_interval_minutes=row.capture_interval_minutes,
        last_online=status.last_online,
        next_online=status.next_online,
    )


def _status_from_parts(public_id, image_row, reading_row, battery_value=None) -> StationStatus:
    """Build a StationStatus from the latest image + latest reading + latest battery.

    Battery is the most recent value of the station's ``battery`` datastream
    (passed in by the caller); the firmware/wake labels come off the reading
    envelope.
    """
    capture = None
    if image_row is not None:
        capture = {
            "timestamp": iso_utc(image_row.captured_at),
            "url": f"/stations/{public_id}/images/{image_row.filename}",
        }

    latest_at = None
    next_online = None
    candidates = []
    if image_row is not None:
        candidates.append((image_row.captured_at, image_row.next_online))
    if reading_row is not None:
        candidates.append((reading_row.recorded_at, reading_row.next_online))
    for ts, nxt in candidates:
        if latest_at is None or ts > latest_at or (ts == latest_at and nxt):
            latest_at = ts
            next_online = nxt

    return StationStatus(
        capture=capture,
        battery=_coerce_battery(battery_value),
        last_online=iso_utc(latest_at) if latest_at else None,
        next_online=iso_utc(next_online) if next_online else None,
        firmware_version=_str_or_none(reading_row.firmware_version) if reading_row is not None else None,
        wake_reason=_str_or_none(reading_row.wake_reason) if reading_row is not None else None,
    )


def _str_or_none(value) -> str | None:
    return value if isinstance(value, str) and value else None


def _latest_image(session, station_id):
    return session.scalar(
        select(StationImage)
        .where(StationImage.station_id == station_id)
        .order_by(StationImage.captured_at.desc())
        .limit(1)
    )


def _latest_reading(session, station_id):
    return session.scalar(
        select(SensorReading)
        .where(SensorReading.station_id == station_id)
        .order_by(SensorReading.recorded_at.desc())
        .limit(1)
    )


def _latest_metric_value(session, station_id, metric, channel=DEFAULT_CHANNEL):
    """Most recent observed value for one (station, metric, channel), or None."""
    return session.scalar(
        select(Observation.value)
        .join(Datastream, Observation.datastream_id == Datastream.id)
        .where(
            Datastream.station_id == station_id,
            Datastream.metric == metric,
            Datastream.channel == channel,
        )
        .order_by(Observation.recorded_at.desc())
        .limit(1)
    )


def resolve_datastream(session, station_id, metric, channel=DEFAULT_CHANNEL) -> Datastream:
    """Get the (station, metric, channel) datastream, creating it on first sight.

    The unit is resolved from the metric registry at creation and frozen on the
    row, so stored history stays self-describing even if the registry changes.
    """
    datastream = session.scalar(
        select(Datastream).where(
            Datastream.station_id == station_id,
            Datastream.metric == metric,
            Datastream.channel == channel,
        )
    )
    if datastream is None:
        datastream = Datastream(
            station_id=station_id, metric=metric, channel=channel, unit=metric_unit(metric)
        )
        session.add(datastream)
        session.flush()
    return datastream


# ----- access ----------------------------------------------------------------

def station_exists(public_id: str) -> bool:
    with session_scope() as session:
        return _station(session, public_id) is not None


def can_view(public_id: str, user) -> bool:
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            return False
        if row.is_public:
            return True
        if user is None:
            return False
        if getattr(user, "is_admin", False):
            return True
        return str(row.owner_id) == getattr(user, "owner_id", None)


def station_owner_id(public_id: str) -> str | None:
    with session_scope() as session:
        row = _station(session, public_id)
        return str(row.owner_id) if row is not None else None


# ----- stations: read --------------------------------------------------------

def latest_status(public_id: str) -> StationStatus:
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            return StationStatus()
        return _status_from_parts(
            public_id,
            _latest_image(session, row.id),
            _latest_reading(session, row.id),
            _latest_metric_value(session, row.id, "battery"),
        )


def station_view(public_id: str) -> tuple[str, AppConfig, StationStatus] | None:
    """Return (url_slug, AppConfig, StationStatus) for one station, or None."""
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            return None
        status = _status_from_parts(
            public_id,
            _latest_image(session, row.id),
            _latest_reading(session, row.id),
            _latest_metric_value(session, row.id, "battery"),
        )
        return row.url_slug, _config_from_row(row, status), status


def station_config(public_id: str) -> AppConfig | None:
    view = station_view(public_id)
    return view[1] if view is not None else None


def list_station_views(user) -> list[tuple[str, str, AppConfig, StationStatus, bool]]:
    """Return (public_id, url_slug, AppConfig, StationStatus, can_edit) per viewable station.

    `can_edit` is True when the caller is an admin or the station's owner.

    Three queries total regardless of station count: the visible stations, then
    the latest image and latest reading per station — no N+1.
    """
    with session_scope() as session:
        stations = session.scalars(select(Station).order_by(Station.url_slug)).all()
        if not stations:
            return []

        owner_id = getattr(user, "owner_id", None) if user is not None else None
        is_admin = bool(getattr(user, "is_admin", False)) if user is not None else False
        visible = [
            s for s in stations
            if s.is_public or is_admin or (owner_id is not None and str(s.owner_id) == owner_id)
        ]
        if not visible:
            return []
        ids = [s.id for s in visible]

        # SQLite has no DISTINCT ON, so rank each station's rows newest-first with
        # a window function and keep rank 1 — still one query per kind, no N+1.
        img_rank = func.row_number().over(
            partition_by=StationImage.station_id,
            order_by=(StationImage.captured_at.desc(), StationImage.id.desc()),
        )
        img_subq = (
            select(StationImage, img_rank.label("rn"))
            .where(StationImage.station_id.in_(ids))
            .subquery()
        )
        ranked_image = aliased(StationImage, img_subq)
        latest_images = {
            img.station_id: img
            for img in session.scalars(select(ranked_image).where(img_subq.c.rn == 1))
        }

        read_rank = func.row_number().over(
            partition_by=SensorReading.station_id,
            order_by=(SensorReading.recorded_at.desc(), SensorReading.id.desc()),
        )
        read_subq = (
            select(SensorReading, read_rank.label("rn"))
            .where(SensorReading.station_id.in_(ids))
            .subquery()
        )
        ranked_reading = aliased(SensorReading, read_subq)
        latest_readings = {
            r.station_id: r
            for r in session.scalars(select(ranked_reading).where(read_subq.c.rn == 1))
        }

        # Latest battery value per station, from the battery datastream's
        # observations — same windowed-rank trick, still one query (no N+1).
        batt_rank = func.row_number().over(
            partition_by=Datastream.station_id,
            order_by=(Observation.recorded_at.desc(), Observation.id.desc()),
        )
        batt_subq = (
            select(
                Datastream.station_id.label("station_id"),
                Observation.value.label("value"),
                batt_rank.label("rn"),
            )
            .join(Observation, Observation.datastream_id == Datastream.id)
            .where(
                Datastream.station_id.in_(ids),
                Datastream.metric == "battery",
                Datastream.channel == DEFAULT_CHANNEL,
            )
            .subquery()
        )
        latest_batteries = {
            row.station_id: row.value
            for row in session.execute(
                select(batt_subq.c.station_id, batt_subq.c.value).where(batt_subq.c.rn == 1)
            )
        }

        result = []
        for s in visible:
            status = _status_from_parts(
                s.public_id, latest_images.get(s.id), latest_readings.get(s.id), latest_batteries.get(s.id)
            )
            can_edit = is_admin or (owner_id is not None and str(s.owner_id) == owner_id)
            result.append((s.public_id, s.url_slug, _config_from_row(s, status), status, can_edit))
        return result


def image_captures(public_id: str, count: int) -> list[dict[str, str]]:
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            return []
        images = session.scalars(
            select(StationImage)
            .where(StationImage.station_id == row.id)
            .order_by(StationImage.captured_at.desc())
            .limit(count)
        ).all()
    return [
        {"timestamp": iso_utc(img.captured_at), "url": f"/stations/{public_id}/images/{img.filename}"}
        for img in reversed(images)
    ]


def sensor_readings(public_id: str, hours: int) -> list[dict[str, object]]:
    """Per-(metric, channel) history series for a station within the lookback window.

    Returns one dict per datastream: ``{metric, channel, unit, points}`` where
    ``points`` is an oldest-to-newest list of ``{timestamp, value}``.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            return []
        rows = session.execute(
            select(
                Datastream.metric,
                Datastream.channel,
                Datastream.unit,
                Observation.recorded_at,
                Observation.value,
            )
            .join(Observation, Observation.datastream_id == Datastream.id)
            .where(Datastream.station_id == row.id, Observation.recorded_at >= cutoff)
            .order_by(Datastream.metric, Datastream.channel, Observation.recorded_at.asc())
        ).all()

    series: dict[tuple[str, str], dict[str, object]] = {}
    order: list[tuple[str, str]] = []
    for metric, channel, unit, recorded_at, value in rows:
        key = (metric, channel)
        if key not in series:
            series[key] = {"metric": metric, "channel": channel, "unit": unit, "points": []}
            order.append(key)
        series[key]["points"].append({"timestamp": iso_utc(recorded_at), "value": value})
    return [series[key] for key in order]


# ----- stations: write -------------------------------------------------------

def create_station(payload, owner_id: str) -> str:
    """Create a station owned by the given user; returns its opaque public_id."""
    with session_scope() as session:
        public_id = _new_public_id(session)
        session.add(
            Station(
                public_id=public_id,
                url_slug=_unique_url_slug(session, payload.title),
                owner_id=uuid.UUID(owner_id),
                title=payload.title,
                location=payload.location,
                country=payload.country,
                country_emoji=payload.country_emoji,
                lat=payload.lat,
                lon=payload.lon,
                alt=payload.alt,
                is_public=payload.is_public,
            )
        )
        return public_id


def save_station_config(public_id: str, config: AppConfig) -> None:
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            raise LookupError(f"Unknown station {public_id!r}")
        title_changed = config.title != row.title
        for column in _CONFIG_COLUMNS:
            setattr(row, column, getattr(config, column))
        # A rename moves the pretty URL (old URL is not preserved); the stable
        # public_id is unchanged, so devices/links/files are unaffected.
        if title_changed:
            row.url_slug = _unique_url_slug(session, config.title, exclude_id=row.id)


def append_image(public_id, *, filename, content_type, size_bytes, captured_at, next_online=None) -> None:
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            raise LookupError(f"Unknown station {public_id!r}")
        values = dict(
            station_id=row.id,
            filename=filename,
            stream=stream_from_filename(filename),
            content_type=content_type,
            size_bytes=size_bytes,
            captured_at=parse_iso_timestamp(captured_at),
            next_online=parse_iso_timestamp(next_online),
            storage_key=f"{public_id}/images/{filename}",
        )
        # Re-upload of the same capture minute updates the row instead of
        # duplicating the timeline entry.
        stmt = sqlite_insert(StationImage).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[StationImage.station_id, StationImage.filename],
            set_={
                "stream": stmt.excluded.stream,
                "content_type": stmt.excluded.content_type,
                "size_bytes": stmt.excluded.size_bytes,
                "captured_at": stmt.excluded.captured_at,
                "next_online": stmt.excluded.next_online,
                "storage_key": stmt.excluded.storage_key,
            },
        )
        session.execute(stmt)


def append_reading(
    public_id,
    timestamp,
    metrics,
    *,
    channel=DEFAULT_CHANNEL,
    firmware_version=None,
    wake_reason=None,
    next_online=None,
) -> None:
    """Persist one device check-in: an envelope row plus one observation per metric.

    ``metrics`` is the numeric measurement dict; each entry resolves (creating if
    needed) the (station, metric, channel) datastream and appends an observation.
    Null values are skipped; booleans are stored as 0/1.
    """
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            raise LookupError(f"Unknown station {public_id!r}")
        recorded_at = parse_iso_timestamp(timestamp)
        reading = SensorReading(
            station_id=row.id,
            recorded_at=recorded_at,
            next_online=parse_iso_timestamp(next_online),
            firmware_version=firmware_version,
            wake_reason=wake_reason,
        )
        session.add(reading)
        session.flush()  # assign reading.id for the observation FK
        for metric, value in (metrics or {}).items():
            if value is None:
                continue
            datastream = resolve_datastream(session, row.id, metric, channel)
            session.add(
                Observation(
                    datastream_id=datastream.id,
                    reading_id=reading.id,
                    recorded_at=recorded_at,
                    value=float(value),
                )
            )


# ----- device secrets --------------------------------------------------------

def read_device_secret_b64(public_id: str) -> str | None:
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            return None
        secret = session.scalar(
            select(StationDeviceSecret)
            .where(
                StationDeviceSecret.station_id == row.id,
                (StationDeviceSecret.expires_at.is_(None)) | (StationDeviceSecret.expires_at > now),
            )
            .order_by(StationDeviceSecret.created_at.desc())
            .limit(1)
        )
        # NOTE: stored as raw base64url bytes for now. Envelope-encrypting these
        # at rest with a server key (APP_SECRET_KEY) is a planned hardening step.
        return secret.secret_enc.decode("ascii") if secret is not None else None


def provision_device_secret(public_id: str) -> str:
    from station_hmac import generate_device_hmac_secret_b64  # lazy: avoid import cycle

    secret_b64 = generate_device_hmac_secret_b64()
    with session_scope() as session:
        row = _station(session, public_id)
        if row is None:
            raise LookupError(f"Unknown station {public_id!r}")
        # Single active secret (immediate rotation).
        session.execute(delete(StationDeviceSecret).where(StationDeviceSecret.station_id == row.id))
        session.add(StationDeviceSecret(station_id=row.id, secret_enc=secret_b64.encode("ascii")))
    return secret_b64


# ----- users -----------------------------------------------------------------

def _user_dict(row: User) -> dict:
    return {
        "email": row.email,
        "is_admin": row.is_platform_admin,
        "plan": row.plan,
        "created_at": iso_utc(row.created_at),
        "owner_id": str(row.id),
    }


def user_has_any() -> bool:
    with session_scope() as session:
        return bool(session.scalar(select(func.count()).select_from(User)))


def user_get(email: str) -> dict | None:
    with session_scope() as session:
        row = session.scalar(select(User).where(User.email == email.strip().lower()))
        return _user_dict(row) if row is not None else None


def user_authenticate(email: str, password: str) -> dict | None:
    from users import _DUMMY_PASSWORD_HASH  # lazy: reuse the shared timing dummy

    with session_scope() as session:
        row = session.scalar(select(User).where(User.email == email.strip().lower()))
        if row is None:
            verify_secret(password, _DUMMY_PASSWORD_HASH)  # constant-time vs known user
            return None
        if not verify_secret(password, row.password_hash):
            return None
        return _user_dict(row)


def user_create(email: str, password: str, *, is_admin: bool = False) -> dict:
    email = email.strip().lower()
    if not email:
        raise ValueError("Email must not be empty.")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    with session_scope() as session:
        if session.scalar(select(User).where(User.email == email)) is not None:
            raise ValueError("A user with that email already exists.")
        user = User(
            email=email,
            password_hash=hash_secret(password),
            is_platform_admin=is_admin,
        )
        session.add(user)
        session.flush()
        return _user_dict(user)
