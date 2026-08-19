"""SQLite engine/session factory for the control plane.

A single local SQLite file holds the control-plane data. The route handlers stay
`def`/sync and FastAPI runs them in a threadpool, so the blocking DB calls don't
stall the event loop.

SQLite is a deliberate commitment, not a default: the repositories use
sqlite-dialect upserts, and the deployment is single-node anyway (image blobs
and the nonce DB are local files). get_engine() therefore refuses any
non-sqlite DATABASE_URL up front. The ORM models keep generic column types, so
a future move to another database stays contained to the db/ package.

The database location comes from DATABASE_URL when set (must be a sqlite URL;
e.g. tests point it at a throwaway file); otherwise it defaults to
``<APP_DATA_DIR>/control.db`` so local dev needs no configuration. The schema
is owned by the Alembic migrations and brought up to head at startup (see
db.migrate.run_migrations).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from settings import get_settings


def database_url() -> str:
    """SQLAlchemy URL for the control-plane database.

    DATABASE_URL wins when set (sqlite only — get_engine enforces it); otherwise
    default to a SQLite file in the data directory. The parent dir is created so
    the file can be opened.
    """
    settings = get_settings()
    if settings.database_url:
        return settings.database_url
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(settings.data_dir / 'control.db').as_posix()}"


_engine: Engine | None = None
_sessionmaker: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Lazily build (once) the process-wide engine + session factory."""
    global _engine, _sessionmaker
    if _engine is None:
        url = database_url()
        # Fail fast with a clear message instead of dying later on the first
        # sqlite-dialect upsert (see module docstring).
        if make_url(url).get_backend_name() != "sqlite":
            raise RuntimeError(
                "DATABASE_URL must be a sqlite:// URL — the data layer is SQLite-only "
                "(see db/session.py)."
            )
        # check_same_thread=False: FastAPI runs the sync route handlers across a threadpool.
        _engine = create_engine(url, future=True, connect_args={"check_same_thread": False})

        # Per-connection SQLite pragmas:
        # - foreign_keys: enforces the ON DELETE CASCADEs; off by default.
        # - journal_mode=WAL: readers don't block the writer, so concurrent
        #   device uploads + page loads don't throw "database is locked".
        #   (Persistent per DB file, but cheap to re-assert per connection.)
        # - synchronous=NORMAL: the recommended pairing with WAL.
        # - busy_timeout: wait for a competing writer instead of failing fast.
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            dbapi_connection.execute("PRAGMA journal_mode=WAL")
            dbapi_connection.execute("PRAGMA synchronous=NORMAL")
            dbapi_connection.execute("PRAGMA busy_timeout=5000")

        _sessionmaker = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commit on success, roll back on error, always close."""
    get_engine()
    assert _sessionmaker is not None  # set by get_engine()
    session = _sessionmaker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
