"""Shared station access checks used by route modules."""

from fastapi import HTTPException, status

from config import get_data_dir, read_station_config, read_station_owner


def require_station_exists(station_id: str) -> None:
    """Raise 404 if no directory has been created for this station."""
    if not (get_data_dir() / station_id).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown station id.",
        )


def can_view_station(station_id: str, user) -> bool:
    """A caller may view a station if it is public, owned by them, or they are admin."""
    data_dir = get_data_dir()
    if not (data_dir / station_id).exists():
        return False

    config = read_station_config(data_dir, station_id)
    if config.is_public:
        return True
    if user is None:
        return False
    if user.is_admin:
        return True
    return read_station_owner(data_dir, station_id) == user.username


def require_station_view(station_id: str, user) -> None:
    """Return 404 instead of 403 when a private station is hidden from the caller."""
    if not can_view_station(station_id, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown station id.",
        )


def require_station_edit(station_id: str, user) -> None:
    """Allow only admins or the station owner to edit a station."""
    require_station_exists(station_id)
    if user.is_admin:
        return
    if read_station_owner(get_data_dir(), station_id) != user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this station.",
        )
