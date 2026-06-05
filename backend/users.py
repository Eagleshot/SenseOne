"""User account storage and authentication (SQLite-backed).

Login identity is the **email address**. The schema is owned by the Alembic
migrations (see db.migrate); this module is a thin layer over db.sqlite_repo plus the
env-var admin bootstrap. ``User.owner_id`` is the user's id that station access checks compare.
"""

import logging
import os
from dataclasses import dataclass

from auth import hash_secret
from db import sqlite_repo

# Precomputed hash with the same PBKDF2 cost as a real one. Used by
# db.sqlite_repo.user_authenticate so the unknown-email path spends the same PBKDF2
# time as a known-user failure, preventing timing-based account enumeration.
_DUMMY_PASSWORD_HASH = hash_secret("eagleshot-dummy-password-for-timing")


@dataclass(frozen=True)
class User:
    email: str
    is_admin: bool
    created_at: str
    owner_id: str = ""  # this user's id; the owner of their stations
    plan: str = "free"  # entitlement plan key (see entitlements.PLANS)


def init_users_db() -> None:
    """Bootstrap an admin from env vars (the schema is owned by the Alembic migrations)."""
    bootstrap_admin_from_env()


def bootstrap_admin_from_env() -> None:
    """Create an admin user from APP_AUTH_EMAIL / APP_AUTH_PASSWORD if no users exist."""
    email = (os.getenv("APP_AUTH_EMAIL") or "").strip()
    password = (os.getenv("APP_AUTH_PASSWORD") or "").strip()
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
    return _user_from_dict(sqlite_repo.user_create(email, password, is_admin=is_admin))


def authenticate_user(email: str, password: str) -> User | None:
    """Return the user record if credentials are valid, else None."""
    result = sqlite_repo.user_authenticate(email, password)
    return _user_from_dict(result) if result is not None else None


def get_user(email: str) -> User | None:
    """Look up a user by email."""
    result = sqlite_repo.user_get(email)
    return _user_from_dict(result) if result is not None else None


def has_any_user() -> bool:
    """True if at least one user exists."""
    return sqlite_repo.user_has_any()


def _user_from_dict(data: dict) -> User:
    return User(
        email=data["email"],
        is_admin=bool(data["is_admin"]),
        created_at=data["created_at"],
        owner_id=data["owner_id"],
        plan=data.get("plan", "free"),
    )
