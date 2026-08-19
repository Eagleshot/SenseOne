"""Runtime status DTO for a station.

``StationStatus`` is the value object the API builds from a station's latest image
and sensor reading; ``_coerce_battery`` normalizes the battery metric. Both are
used by db.station_repo and the route layer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StationStatus:
    """Latest runtime status for a station, derived from its database rows."""

    capture: dict | None = None
    battery: int | None = None
    last_online: str | None = None
    next_online: str | None = None
    firmware_version: str | None = None
    wake_reason: str | None = None


def _coerce_battery(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
