"""API route modules."""

from typing import Annotated

from fastapi import Depends, HTTPException

from utils import sanitize_station_id


def _validate_station_id(station_id: str) -> str:
    """Validate and return the normalized station ID, or raise 400."""
    normalized = sanitize_station_id(station_id)
    if station_id != normalized:
        raise HTTPException(status_code=400, detail="Invalid station id.")
    return normalized


ValidStationId = Annotated[str, Depends(_validate_station_id)]
