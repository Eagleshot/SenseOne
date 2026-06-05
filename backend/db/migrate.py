"""Run Alembic migrations programmatically at application startup.

`create_app()` calls `run_migrations()` instead of creating tables from metadata,
so the control-plane schema is owned by the migration history (see ../migrations).
Idempotent: every boot upgrades to head, which is a no-op when already current.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from db.session import database_url

_BACKEND_DIR = Path(__file__).resolve().parent.parent  # the backend/ package root


def _alembic_config() -> Config:
    """Alembic config pinned to this repo's ini/scripts and the app's DB URL.

    script_location and sqlalchemy.url are set explicitly so the runner works no
    matter the process cwd (local `python main.py`, uvicorn, or the container).
    """
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url())
    return cfg


def run_migrations() -> None:
    """Upgrade the control-plane database to the latest revision."""
    command.upgrade(_alembic_config(), "head")
