"""User account storage and authentication."""

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from auth import hash_secret, verify_secret
from config import get_data_dir

USERS_DB_FILENAME = "users.db"


@dataclass(frozen=True)
class User:
    username: str
    is_admin: bool
    created_at: str


def users_db_path() -> Path:
    """Path to the users SQLite database."""
    return get_data_dir() / USERS_DB_FILENAME


def _connect() -> sqlite3.Connection:
    path = users_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_users_db() -> None:
    """Create the users table if it doesn't exist and bootstrap an admin from env vars."""
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
    bootstrap_admin_from_env()


def bootstrap_admin_from_env() -> None:
    """Create an admin user from APP_AUTH_USERNAME / APP_AUTH_PASSWORD if no users exist."""
    username = (os.getenv("APP_AUTH_USERNAME") or "").strip()
    password = (os.getenv("APP_AUTH_PASSWORD") or "").strip()
    if not username or not password:
        return
    with _connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        if row["count"] > 0:
            return
    try:
        create_user(username, password, is_admin=True)
        logging.info("Bootstrap admin user %r created from environment.", username)
    except ValueError as exc:
        logging.error("Failed to bootstrap admin user: %s", exc)


def create_user(username: str, password: str, *, is_admin: bool = False) -> User:
    """Insert a new user. Raises ValueError if the username already exists."""
    username = username.strip()
    if not username:
        raise ValueError("Username must not be empty.")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    created_at = datetime.now(timezone.utc).isoformat()
    password_hash = hash_secret(password)
    with _connect() as connection:
        try:
            connection.execute(
                "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, 1 if is_admin else 0, created_at),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("A user with that username already exists.") from exc
    return User(username=username, is_admin=is_admin, created_at=created_at)


def authenticate_user(username: str, password: str) -> User | None:
    """Return the user record if credentials are valid, else None."""
    username = username.strip()
    with _connect() as connection:
        row = connection.execute(
            "SELECT username, password_hash, is_admin, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None:
        # Run a dummy verify to keep timing similar between known/unknown usernames.
        verify_secret(password, None)
        return None
    if not verify_secret(password, row["password_hash"]):
        return None
    return User(
        username=row["username"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )


def get_user(username: str) -> User | None:
    """Look up a user by username."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT username, is_admin, created_at FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if row is None:
        return None
    return User(
        username=row["username"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )


def has_any_user() -> bool:
    """True if at least one user exists."""
    with _connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    return row["count"] > 0
