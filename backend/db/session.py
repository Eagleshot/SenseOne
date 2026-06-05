"""SQLite engine/session factory for the control plane.

A single local SQLite file holds the control-plane data. The route handlers stay
`def`/sync and FastAPI runs them in a threadpool, so the blocking DB calls don't
stall the event loop.

The database location comes from DATABASE_URL when set (e.g. tests point it at a
throwaway file); otherwise it defaults to ``<APP_DATA_DIR>/control.db`` so local
dev needs no configuration. The schema is owned by the Alembic migrations and
brought up to head at startup (see db.migrate.run_migrations).
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import get_data_dir


def database_url() -> str:
    """SQLAlchemy URL for the control-plane database.

    DATABASE_URL wins when set; otherwise default to a SQLite file in the data
    directory. The parent dir is created so the file can be opened.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'control.db').as_posix()}"


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

        # SQLite enforces foreign keys (the ON DELETE CASCADEs) only when this
        # pragma is set, and it must be set per connection.
        @event.listens_for(_engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

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
