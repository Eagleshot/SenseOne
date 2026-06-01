"""Create a station directly in the backend data directory."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from config import ensure_station_dir, get_data_dir, write_station_config, write_station_meta
from models import AppConfig
from utils import sanitize_station_id, unique_station_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a SenseOne station config and database directory.",
    )
    parser.add_argument("--title", required=True, help="Display name shown in the UI.")
    parser.add_argument("--station-id", help="Stable station id. Defaults to a sanitized title.")
    parser.add_argument("--location", default="", help="Place name shown in the UI.")
    parser.add_argument("--country", default="", help="Country name shown in the UI.")
    parser.add_argument("--country-emoji", default="", help="Optional flag or short country marker.")
    parser.add_argument("--lat", type=float, default=0.0, help="Latitude in decimal degrees.")
    parser.add_argument("--lon", type=float, default=0.0, help="Longitude in decimal degrees.")
    parser.add_argument("--alt", type=float, default=0.0, help="Altitude in metres.")
    parser.add_argument("--owner", help="Username that owns this station.")
    parser.add_argument("--public", action="store_true", help="Make the station visible to anonymous visitors.")
    parser.add_argument("--data-dir", help="Override APP_DATA_DIR for this run.")
    parser.add_argument(
        "--auto-suffix",
        action="store_true",
        help="Append -2, -3, etc. if the station id already exists.",
    )
    return parser.parse_args()


def validate_coordinates(lat: float, lon: float) -> None:
    if not -90 <= lat <= 90:
        raise SystemExit("--lat must be between -90 and 90.")
    if not -180 <= lon <= 180:
        raise SystemExit("--lon must be between -180 and 180.")


def main() -> None:
    args = parse_args()
    title = args.title.strip()
    if not title:
        raise SystemExit("--title must not be empty.")

    validate_coordinates(args.lat, args.lon)

    if args.data_dir:
        os.environ["APP_DATA_DIR"] = str(Path(args.data_dir).resolve())

    data_dir = get_data_dir()
    owner = args.owner.strip() if args.owner else ""
    requested_id = args.station_id or title
    if args.auto_suffix:
        station_id = unique_station_id(data_dir, requested_id)
        if station_id is None:
            raise SystemExit("Could not create a unique station id.")
    else:
        station_id = sanitize_station_id(requested_id)
    station_root = data_dir / station_id

    if station_root.exists():
        raise SystemExit(
            f"Station '{station_id}' already exists. Use --auto-suffix or choose another --station-id."
        )

    config = AppConfig(
        title=title,
        location=args.location,
        country=args.country,
        country_emoji=args.country_emoji,
        lat=args.lat,
        lon=args.lon,
        alt=args.alt,
        is_public=args.public,
    )

    ensure_station_dir(data_dir, station_id)
    write_station_config(data_dir, station_id, config)
    if owner:
        write_station_meta(data_dir, station_id, owner=owner)

    print(f"Created station: {station_id}")
    print(f"Data directory: {station_root}")
    print(f"Visibility: {'public' if config.is_public else 'private'}")
    if owner:
        print(f"Owner: {owner}")


if __name__ == "__main__":
    main()
