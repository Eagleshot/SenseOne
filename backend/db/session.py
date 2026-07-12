"""SQLite engine/session factory for the control plane.

A single local SQLite file holds the control-plane data. The route handlers stay
`def`/sync and FastAPI runs them in a threadpool, so the blocking DB calls don't
stall the event loop.

The database location comes from DATABASE_URL when set (e.g. tests point it at a
throwaway file); otherwise it defaults to ``<APP_DATA_DIR>/control.db`` so local
dev needs no configuration. The schema is owned by the Alembic migrations and
brought up to head at startup (see db.migrate.run_migrations).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from settings import get_settings


def database_url() -> str:
    """SQLAlchemy URL for the control-plane database.

    DATABASE_URL wins when set; otherwise default to a SQLite file in the data
    directory. The parent dir is created so the file can be opened.
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
        # check_same_thread=False: FastAPI runs the sync route handlers across a threadpool.
        _engine = create_engine(
            database_url(), future=True, connect_args={"check_same_thread": False}
        )

        # Per-connection SQLite pragmas (skipped if DATABASE_URL points elsewhere):
        # - foreign_keys: enforces the ON DELETE CASCADEs; off by default.
        # - journal_mode=WAL: readers don't block the writer, so concurrent
        #   device uploads + page loads don't throw "database is locked".
        #   (Persistent per DB file, but cheap to re-assert per connection.)
        # - synchronous=NORMAL: the recommended pairing with WAL.
        # - busy_timeout: wait for a competing writer instead of failing fast.
        if _engine.url.get_backend_name() == "sqlite":

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
