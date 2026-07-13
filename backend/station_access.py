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
    return sqlite_repo.owner_or_admin(sqlite_repo.station_owner_id(station_id), user)


def require_station_edit(station_id: str, user) -> None:
    """Allow only admins or the owning user to edit a station.

    Hides existence like require_station_view: a caller who can't even view the
    station (private and not theirs) gets 404, not 403, so edit routes can't be
    used to probe which private station ids exist. A viewable-but-not-editable
    station (public, owned by someone else) legitimately gets 403.
    """
    owner_id = sqlite_repo.station_owner_id(station_id)
    if owner_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown station id.")
    if sqlite_repo.owner_or_admin(owner_id, user):
        return
    if not can_view_station(station_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown station id.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this station.",
    )
