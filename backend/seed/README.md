# Seeding mock data

Populates the **SQLite** control plane with realistic sample stations so you can
run the app locally without real cameras/devices: owner users, stations, sensor
history, and timeline image rows — plus the image blobs on disk.

- [`seed_mock_data.py`](seed_mock_data.py) — the runnable seeder (writes the SQLite DB).
- [`mock_data.py`](mock_data.py) — the source data: the `WEBCAM_SEED` station list,
  `generate_historical_data()`, and the sample-image helpers.

## What it writes

- **SQLite rows:** `users` (owners), `stations`, `sensor_readings` plus
  `datastreams` / `observations` (the numeric metrics), `station_images`.
- **Disk:** the timeline image blobs only, under `<data-dir>/<public_id>/images/`
  (`storage_key = "<public_id>/images/<filename>"`). All metadata is in the SQLite
  control DB, so nothing else is written to disk.

Per station it generates `--count` timeline images (default 16, 30 min apart) and
`168` hours of hourly sensor readings (`temperature`, `humidity`, `pressure`,
`battery`, `reception`, `voltage`, `deviceTemperature`, `firmwareVersion`,
`wakeReason`). The latest reading carries a `next_online` hint from the seed
entry's `nextUpdateMinutesIn`.

## How to run

The seeder creates the schema itself, so there's no separate setup. From
`backend/`:

```powershell
python seed/seed_mock_data.py --overwrite
```

By default it writes the same SQLite file the app uses
(`<APP_DATA_DIR>/control.db`, i.e. `backend/data/control.db`). Or run it inside
the container (writes to the data volume):

```powershell
docker compose run --rm backend python seed/seed_mock_data.py --overwrite
```

### CLI flags

| Flag | Default | Purpose |
|---|---|---|
| `--database-url <url>` | `$DATABASE_URL` | Override the database the app/seeder use (any SQLAlchemy URL). |
| `--data-dir <path>` | `backend/data` | Where image blobs are written. |
| `--count <n>` | `16` | Timeline images per station. |
| `--overwrite` | off | Clear + regenerate each station's readings/images. |
| `--station-id <id>` | all | Seed only this station id (repeatable). |
| `--owner-password <pw>` | `devpassword123` | Password for newly-created owners (≥ 12 chars). |

## Seeded logins

Owners come from the `owner` (email) field on the seed entries:

| Email | Password |
|---|---|
| `alice@example.com` | `devpassword123` |
| `bob@example.com` | `devpassword123` |

These are **regular (non-admin) users**. An admin is *not* seeded — it's
bootstrapped from `APP_AUTH_EMAIL` / `APP_AUTH_PASSWORD` when no users exist
(see `backend/users.py`).

## Re-running

Idempotent: owners are reused (passwords never reset). Without `--overwrite`,
stations that already have readings/images are left alone. With `--overwrite`,
each station's readings + image rows are cleared and regenerated. For a fully
clean slate, delete the SQLite file (`backend/data/control.db`) and re-seed.

## Customizing / adding a station

Edit `WEBCAM_SEED` in [`mock_data.py`](mock_data.py); each entry's `id` becomes
the station's `url_slug` (the opaque `public_id` is generated automatically),
`owner` is the owner email (omit for an unowned public station, which lands under
the shared `demo@example.com` owner). Then run the seeder (optionally with
`--station-id <url_slug>`). Sample images download from Unsplash on first run,
falling back to an embedded placeholder offline.
