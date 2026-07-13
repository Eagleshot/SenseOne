"""User account storage and authentication (SQLite-backed).

Login identity is the **email address**. The schema is owned by the Alembic
migrations (see db.migrate); this module is a thin layer over db.sqlite_repo plus the
env-var admin bootstrap. ``User.owner_id`` is the user's id that station access checks compare.
"""

import logging
from functools import cache

from security import hash_secret
from db import sqlite_repo
from settings import get_settings
from user_db import User


@cache
def _dummy_password_hash() -> str:
    """A hash with the same PBKDF2 cost as a real one, so db.sqlite_repo's
    unknown-email login path spends the same time as a known-user failure
    (timing-based account-enumeration defense).

    Computed on first use (and cached), not at import: importing this module —
    which every route module does transitively — otherwise pays ~600k PBKDF2
    iterations at boot even for processes that never hit the login path.
    """
    return hash_secret("eagleshot-dummy-password-for-timing")


def __getattr__(name: str):
    # Preserve the module-level ``_DUMMY_PASSWORD_HASH`` name (used by
    # db.sqlite_repo and tests) while deferring its cost to first access.
    if name == "_DUMMY_PASSWORD_HASH":
        return _dummy_password_hash()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def init_users_db() -> None:
    """Bootstrap an admin from env vars (the schema is owned by the Alembic migrations)."""
    bootstrap_admin_from_env()


def bootstrap_admin_from_env() -> None:
    """Create an admin user from APP_AUTH_EMAIL / APP_AUTH_PASSWORD if no users exist."""
    settings = get_settings()
    email = settings.auth_email
    password = settings.auth_password
    if not email or not password:
        return
    if has_any_user():
        return
    try:
        create_user(email, password, is_admin=True)
        logging.info("Bootstrap admin user %r created from environment.", email)
    except ValueError as exc:
        logging.error("Failed to bootstrap admin user: %s", exc)


def create_user(email: str, password: str, *, is_admin: bool = False) -> User:
    """Insert a new user. Raises ValueError if the email already exists."""
    return sqlite_repo.user_create(email, password, is_admin=is_admin)


def authenticate_user(email: str, password: str) -> User | None:
    """Return the user record if credentials are valid, else None."""
    return sqlite_repo.user_authenticate(email, password)


def get_user(email: str) -> User | None:
    """Look up a user by email."""
    return sqlite_repo.user_get(email)


def get_session_user(token_hash: str) -> User | None:
    """The user behind a valid, unexpired session token hash (one joined query)."""
    return sqlite_repo.session_user(token_hash)


# Once a user exists, that fact never reverts (there is no user deletion), so
# remember it instead of querying on every request — get_optional_current_user
# otherwise costs a COUNT per anonymous call. If user deletion is ever added,
# this cache must be invalidated there. Tests reset it via _reset_user_cache().
_known_to_have_users = False


def has_any_user() -> bool:
    """True if at least one user exists."""
    global _known_to_have_users
    if _known_to_have_users:
        return True
    if sqlite_repo.user_has_any():
        _known_to_have_users = True
    return _known_to_have_users


def _reset_user_cache() -> None:
    """Forget the cached 'users exist' fact (test harness only; the DB was wiped)."""
    global _known_to_have_users
    _known_to_have_users = False
