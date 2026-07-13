"""Typed user projection returned by the repository and used across the app.

Kept separate from the SQLAlchemy ORM ``User`` row (db.models.User) — which also
holds the password hash — this is the read-only, hash-free shape the rest of the
app passes around. Mirrors station_db.StationStatus: a plain dataclass the
repository builds and returns, so the data layer needn't import the app layer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    email: str
    is_admin: bool
    created_at: str
    owner_id: str = ""  # this user's id; the owner of their stations
    plan: str = "free"  # entitlement plan key (see entitlements.PLANS)
