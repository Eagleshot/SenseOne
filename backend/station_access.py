"""Shared station access checks used by route modules (SQLite-backed)."""

from fastapi import HTTPException, status

from db import sqlite_repo


def require_station_exists(station_id: str) -> None:
    """Raise 404 if the station does not exist."""
    if not sqlite_repo.station_exists(station_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown station id.")


def can_view_station(station_id: str, user) -> bool:
    """A caller may view a station if it is public, owned by them, or they are admin."""
    return sqlite_repo.can_view(station_id, user)


def require_station_view(station_id: str, user) -> None:
    """Return 404 instead of 403 when a private station is hidden from the caller."""
    if not can_view_station(station_id, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown station id.",
        )


def can_edit_station(station_id: str, user) -> bool:
    """True if the caller may edit the station (admin or its owner)."""
    if user is None:
        return False
    if getattr(user, "is_admin", False):
        return True
    return sqlite_repo.station_owner_id(station_id) == getattr(user, "owner_id", None)


def require_station_edit(station_id: str, user) -> None:
    """Allow only admins or the owning user to edit a station."""
    require_station_exists(station_id)
    if user.is_admin:
        return
    if sqlite_repo.station_owner_id(station_id) == getattr(user, "owner_id", None):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this station.",
    )
