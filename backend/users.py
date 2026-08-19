"""App-level user helpers: env-var admin bootstrap and the users-exist cache.

Login identity is the **email address**. Storage lives in db.user_repo; this
module holds only what sits above it — bootstrapping the first admin from
APP_AUTH_EMAIL / APP_AUTH_PASSWORD, and caching the "at least one user exists"
fact that anonymous requests would otherwise re-query.
"""

import logging

from db import user_repo
from settings import get_settings


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
        user_repo.user_create(email, password, is_admin=True)
        logging.info("Bootstrap admin user %r created from environment.", email)
    except ValueError as exc:
        logging.error("Failed to bootstrap admin user: %s", exc)


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
    if user_repo.user_has_any():
        _known_to_have_users = True
    return _known_to_have_users


def _reset_user_cache() -> None:
    """Forget the cached 'users exist' fact (test harness only; the DB was wiped)."""
    global _known_to_have_users
    _known_to_have_users = False
