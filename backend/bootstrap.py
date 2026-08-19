"""Bootstrap a fresh deployment: admin user + station + device secret.

Creates (or reuses) an owner account, a station owned by it, and a one-time
device HMAC secret to flash to the firmware. The script brings the schema up to
head itself (via db.migrate.run_migrations, the same path the app uses at
startup), so no separate setup is needed; by default it writes the same SQLite
control DB the app uses.

Email / password fall back to APP_AUTH_EMAIL / APP_AUTH_PASSWORD when omitted, so
a deployment that already sets those for the app's own admin bootstrap can run
this with just a --title.

Run from `backend/`:
    python bootstrap.py --title "Silvretta Glacier" --lat 46.85 --lon 10.08 --public
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import station_repo, user_repo  # noqa: E402
from db.migrate import run_migrations  # noqa: E402
from models import StationCreateRequest  # noqa: E402
from settings import get_settings  # noqa: E402
from station_hmac import provision_device_hmac_secret  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the first admin user, a station, and its device HMAC secret."
    )
    parser.add_argument("--title", required=True, help="Station title; the station id/slug is derived from it.")
    parser.add_argument("--email", default=get_settings().auth_email or None, help="Admin email (default: APP_AUTH_EMAIL).")
    parser.add_argument(
        "--password",
        default=get_settings().auth_password or None,
        help="Admin password, >=12 chars (default: APP_AUTH_PASSWORD). Only needed when the user does not exist yet.",
    )
    parser.add_argument("--location", default="", help="Place name shown in the UI.")
    parser.add_argument("--country", default="", help="Country name shown in the UI.")
    parser.add_argument("--lat", type=float, default=0.0, help="Latitude in decimal degrees.")
    parser.add_argument("--lon", type=float, default=0.0, help="Longitude in decimal degrees.")
    parser.add_argument("--alt", type=float, default=None, help="Altitude in metres above sea level (omit when unknown).")
    parser.add_argument("--public", action="store_true", help="Make the station visible to anonymous visitors.")
    parser.add_argument("--database-url", help="Override DATABASE_URL for this run.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    email = (args.email or "").strip().lower()
    if not email:
        raise SystemExit("Provide --email (or set APP_AUTH_EMAIL).")
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    run_migrations()  # build/upgrade the schema to head, stamped like the app

    user = user_repo.user_get(email)
    if user is None:
        if not args.password:
            raise SystemExit("No such user yet — pass --password (or set APP_AUTH_PASSWORD) to create the admin.")
        try:
            user = user_repo.user_create(email, args.password, is_admin=True)
        except ValueError as exc:
            raise SystemExit(f"Could not create admin: {exc}")
        print(f"Created admin user {user.email!r}.")
    else:
        print(f"Reusing existing user {user.email!r}.")

    payload = StationCreateRequest(
        title=args.title,
        location=args.location,
        country=args.country,
        lat=args.lat,
        lon=args.lon,
        alt=args.alt,
        is_public=args.public,
    )
    public_id = station_repo.create_station(payload, user.owner_id)
    view = station_repo.station_view(public_id)
    url_slug = view[0] if view else public_id

    secret_b64 = provision_device_hmac_secret(public_id)

    print()
    print("Station created.")
    print(f"  station id : {public_id}")
    print(f"  url slug   : {url_slug}")
    print(f"  owner      : {user.email}")
    print()
    print("Device HMAC secret (shown once - copy it into the firmware now):")
    print(f"  {secret_b64}")


if __name__ == "__main__":
    main()
