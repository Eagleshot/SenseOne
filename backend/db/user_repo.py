"""SQLite repository for users and their auth sessions.

The user/session counterpart to db.station_repo: the `users.py` and `auth.py`
helpers call in here. Synchronous so it slots into the sync route handlers via
FastAPI's threadpool.

Sessions are stored by token *hash* (the caller hashes; see auth.py), so the
control DB never holds a live bearer token.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from security import dummy_password_hash, hash_secret, verify_secret
from db.models import AuthSession, User
from db.session import session_scope
from user_db import User as UserAccount
from utils import iso_utc


# ----- auth sessions ---------------------------------------------------------

def session_create(token_hash: str, email: str, expires_at: datetime) -> None:
    with session_scope() as session:
        session.add(AuthSession(token_hash=token_hash, email=email, expires_at=expires_at))


def session_user(token_hash: str) -> UserAccount | None:
    """The user behind a valid, unexpired session token hash, or None.

    One joined query, used by the per-request auth dependencies instead of a
    session lookup followed by a separate user lookup.
    """
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        row = session.scalar(
            select(User)
            .join(AuthSession, AuthSession.email == User.email)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.expires_at > now,
            )
        )
        return _user_projection(row) if row is not None else None


def session_delete(token_hash: str) -> None:
    with session_scope() as session:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))


def sessions_prune_expired() -> None:
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        session.execute(delete(AuthSession).where(AuthSession.expires_at <= now))


# ----- users -----------------------------------------------------------------

def _user_projection(row: User) -> UserAccount:
    return UserAccount(
        email=row.email,
        is_admin=row.is_platform_admin,
        created_at=iso_utc(row.created_at),
        owner_id=str(row.id),
        plan=row.plan,
    )


def user_has_any() -> bool:
    with session_scope() as session:
        return bool(session.scalar(select(func.count()).select_from(User)))


def user_get(email: str) -> UserAccount | None:
    with session_scope() as session:
        row = session.scalar(select(User).where(User.email == email.strip().lower()))
        return _user_projection(row) if row is not None else None


def user_authenticate(email: str, password: str) -> UserAccount | None:
    with session_scope() as session:
        row = session.scalar(select(User).where(User.email == email.strip().lower()))
        if row is None:
            verify_secret(password, dummy_password_hash())  # constant-time vs known user
            return None
        if not verify_secret(password, row.password_hash):
            return None
        return _user_projection(row)


def user_create(email: str, password: str, *, is_admin: bool = False) -> UserAccount:
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
        return _user_projection(user)
