"""Alembic environment for the Eagleshot control plane.

Schema source of truth is the ORM metadata (db.models.Base.metadata); the URL
defaults to the same place the app uses (db.session.database_url) so the CLI and
the startup runner (db.migrate.run_migrations) target one database. `render_as_batch`
is on because SQLite can't ALTER columns in place — batch mode rebuilds the table.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

from db.models import Base
from db.session import database_url

# Alembic Config object (values from alembic.ini).
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    """Resolve the DB URL: explicit ini/runner value wins, else the app default."""
    return config.get_main_option("sqlalchemy.url") or database_url()


def run_migrations_offline() -> None:
    """Emit SQL without a DBAPI connection (alembic upgrade --sql)."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = create_engine(_url(), poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
