"""Plan entitlements — the single place feature code asks "what is this owner allowed?".

This is a seam, not an enforcement layer: nothing here is wired into upload,
retention, or station-creation yet. The point is that when those gates are built
they call ``limits_for(...)`` instead of hardcoding free-tier behaviour, so turning
on paid tiers becomes data (the owner's ``plan``) rather than code changes.

Limits are resolved from the **owning entity** (a user today; an account later if
that layer is added) so the resolver survives that change. ``station`` is accepted
for future per-station add-ons but is not consulted yet.

Values mirror the pricing table in TODO.md. Treat them as provisional until the
unit-economics / willingness-to-pay work lands.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    """The resolved capability ceiling for one owner (and, later, one station)."""

    max_image_width: int
    max_image_height: int
    min_capture_interval_minutes: int
    image_retention_days: int
    sensor_retention_days: int
    # None means "no included cap" (unlimited, billed per station).
    included_station_count: int | None


# Plan key -> limits. Keys are stored verbatim in users.plan.
PLANS: dict[str, Limits] = {
    "free": Limits(
        max_image_width=640,
        max_image_height=480,
        min_capture_interval_minutes=60,
        image_retention_days=7,
        sensor_retention_days=30,
        # TODO.md pricing table: 3 stations included free, more per-station billed.
        included_station_count=3,
    ),
    "pro": Limits(
        max_image_width=1280,
        max_image_height=720,
        min_capture_interval_minutes=10,
        image_retention_days=180,
        sensor_retention_days=365,
        included_station_count=None,
    ),
    "business": Limits(
        max_image_width=1920,
        max_image_height=1080,
        min_capture_interval_minutes=5,
        image_retention_days=365,
        sensor_retention_days=1095,
        included_station_count=None,
    ),
}

DEFAULT_PLAN = "free"


def plan_for(user) -> str:
    """The plan key for an owner; free for anonymous callers or unknown plans."""
    plan = getattr(user, "plan", None) if user is not None else None
    return plan if plan in PLANS else DEFAULT_PLAN


def limits_for(user, station=None) -> Limits:
    """Resolve the capability limits for an owner (``station`` reserved for add-ons)."""
    return PLANS[plan_for(user)]
