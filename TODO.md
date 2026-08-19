# Next TODOs

- In the free tier, you should only be able to save a set of standard datatypes (TODO define)
- Make a metrics and wake reasons catalog

## Background-job runner (prerequisite for Alerts / retention / reports / time-lapse)

A single asyncio scheduler task started from FastAPI's lifespan — no new dependency, no
separate process. Jobs are plain sync functions run via `asyncio.to_thread`; gate on
`APP_RUN_JOBS` (default true) so a future multi-worker deploy can pin jobs to one instance.
Tests are unaffected (TestClient without `with` never runs lifespan).

1. **Scheduler core** (`backend/jobs/scheduler.py`): `Job` dataclass (name, interval, func,
   last_run/last_error), ~30 s tick loop, every exception caught and logged — a failing job
   must never kill the loop. Log start/duration/outcome per run.
2. **Job 1 — retention sweep** (hourly + once at startup): per station, resolve the owner's
   plan via `limits_for()` (first real consumer of the entitlements seam) and delete
   images/readings past `image_retention_days`/`sensor_retention_days`. Batched deletes
   (~500 rows/tx) to keep SQLite write locks short. Ship with `APP_RETENTION_DRY_RUN=true`
   default and flip after eyeballing one real run (it destroys user data). Phase 2: reap
   orphan blobs (files on disk with no DB row).
3. **Job 2 — offline-alert evaluation** (every 1-5 min): migration `0003` adds
   `alert_rules` (station, type, channel, config) + `alert_state` (current state, last
   transition, last notified) so alerts are edge-triggered (fire on the online<->offline
   transition, not every tick). Detection reuses `is_station_online()`. Dispatch: webhook +
   log first (zero infra), SMTP email second (settings go into `Settings`). Threshold and
   wake-reason alerts become new rule types later.
4. **Tests**: jobs are plain functions — unit-test against the test DB; one scheduler test
   (fake job runs; a raising job doesn't stop the loop).

Order: 1+2 as one PR (scheduler proves itself on retention, dry-run as safety net), then 3
with its migration. Scheduled reports, time-lapse, and cloud backups then become "just
another job".

## Fix the Charts

- Make default Icon depending on the unit
- Make the charts configurable

## Sensors/Data

- Multiple sensors per station (cam/sensor + additional weather station or smart home data or even multiple cameras (e.g. openmv offers thermal + standard))
- Connect to different data sources to back up the data (scheduled or on-upload to cloud storage, e.g. FTP or Google Drive) or external weather services
- User API to get sensor data (e.g. smart home)
- Scheduled reports (weekly PDF/email summary) + public per-station status/uptime.
- Filter stations by data type etc.

## Alerts

- Alerts if station is offline or back online
- Alert if data is above or below a certain threshold
- Alert for specific wake reasons
- Alert if data is above or below a certain threshold for a certain amount of time
- Alert if data is not received for a certain amount of time

-> Add different alerting options (e-mail, slack, sms etc.)

## Image processing

- Add logo + timestamp on the image itself
- Blur on camera (blur region is selected in the frontend and then sent as a mask to the camera, which applies it on capture)
- Automatically detect and blur people (on camera or in the backend using YOLO or similar)
- Custom detection pipeline

## Branding and Design

- Make a new concept for branding and theming
- Add interactive points on the image
- Add the page as a PWA
- Custom Google Maps Link
- Link other Webcams from this Owner
- User can add an external link in the frontend (or profile?)
- Time-lapse video from captures (maybe automatic)
- Embeddable widget / iframe (free tier shows platform badge -> virality).

## Miscellaneous

- Private stations that are owned by the user when logged in should be visible first
- Password protected stations or just viewer accounts
- Maybe even e2ee for the data (no processing)
- The "compare image" should also go into fullscreen like the image and map and use the same timeline component as the image (but permanently visible, not a hover state)
- User can change Units from Metric to Imperial and vice versa

## Hosting / Scaling

- Switch to external image storage (Cloudflare R2 or similar) to simplify scaling
- Use managed auth (e.g. hanko.io)
- Use a managed db (e.g. Cloudflare D1)

## Productization / SaaS tiers
Offer as a hosted service. The **station is the unit of value and of cost** — image storage + bandwidth (biggest), OpenWeather API calls, and compute (blur/detection, time-lapse) all scale per station. So price **per station/month**, with a small number of *capability* plans that unlock features (the costs that aren't per-station: white-label, SSO, custom detection), plus **usage add-ons** for the genuinely variable bits.

-> Do pricing/margin calculations based on the unit economics below, then validate with some customer discovery / willingness-to-pay research.

**Image resolution is the headline ladder.** Higher resolution is the clearest quality difference customers will pay for (1080p vs VGA), so it's the primary thing each tier unlocks — even though, cost-wise, retention and capture interval actually multiply storage more (see Unit economics below).

| Feature / limit | Free | Pro (CHF7/station/mo) | Business (CHF19/station/mo) |
|---|---|---|---|
| Stations | 3 free, then CHF1/station/mo | Unlimited (per-station billing) | Unlimited (per-station billing) |
| Max image resolution | VGA (640×480) | HD 720p (1280×720)* | Full HD 1080p (1920×1080)* |
| Image capture interval | >=60 min | >=10 min* | >=5 min* |
| Image retention | 7 days | 6 months* | 1 year* |
| Sensor capture interval | >=10 min | >=5 min* | >=1 min* |
| Sensor retention | 30 days | 1 year** | 3 years** |
| Map weather overlay + forecast | Current only | Overlay + 5-day | + history |
| Alerts | 1 (offline), email | Threshold + offline, email + webhook | Unlimited + SMS***/Slack/Teams |
| Image processing | Privacy only | + Logo + timestamp watermark | + custom detection pipeline |
| Branding | Platform-branded | Custom logo/colors, link owner's cams + external link | Custom logo/colors, link owner's cams + external link |
| Public page | Public only | Private or password protected | Private or password protected |
| Backup / Bridge | — | CSV | + Scheduled or on-upload to cloud storage |
| Data API | — | Yes (rate-limited) | Yes (higher rate limits) |
| Support | Community | Email | Email / Priority |

- Enterprise (custom): dedicated instance/on-prem/self-host, white-labelling, volume discounts, custom features and detection models etc.

- Usage add-ons (metered, on top of per-station price)
    - `*` Extended image retention/higher resolution (max. 24 MP): CHF/GB-month (based on the incremental storage cost)
    - `**` Sensor retention: CHF/additional year
    - `***` SMS alerts — per-message pass-through (email/webhook are included).

## Coupled changes (landmines)

Deferred couplings that are documented as comments at the code sites; this section is
the index so they're findable when the triggering change happens. Pointers are
file + symbol, not line numbers.

- **User deletion** (none exists today) → invalidate the `users._known_to_have_users`
  cache; delete the user's `auth_sessions` rows (keyed by email, no FK, so they are not
  cascaded); and note `Station.owner_id` is `ON DELETE CASCADE` — deleting a user
  destroys their stations' DB data, while the image blobs need an explicit
  `image_store.delete_prefix` per station (like the delete-station route does).
- **User email change** → `auth_sessions.email` keys break (sessions orphan silently).
  Re-key sessions by user id when this lands.
- **Account/tenant layer** → `users.plan` moves with the owning entity (see the comment
  on `db.models.User.plan`); `entitlements.limits_for` is written to survive this.
- **Enforcing entitlements** → wire `entitlements.limits_for()` into image upload
  (resolution/size), station creation (`included_station_count`), and capture-interval
  validation. Retention is Job 1 of the background-job runner above.
- **Device-secret encryption at rest** → `station_device_secrets.secret_enc` stores the
  raw base64url secret today; envelope encryption with a server key is the planned
  hardening (see `db.models.StationDeviceSecret` and `station_repo.read_device_secret_b64`).
- **Orphan image blobs** → upload writes the blob before the DB row; station delete
  removes the DB row before the blobs — a mid-operation failure leaves orphan files
  either way. Reaped by the retention sweep, phase 2 (background-job runner above).
- **Multi-worker deploy** → per-process state degrades: the login throttle and the
  OpenWeather caches (inventory in the `backend/main.py` docstring; worker count is
  pinned in `backend/Dockerfile`). Jobs must be pinned to one instance via
  `APP_RUN_JOBS` (background-job runner above). Sessions and replay nonces are already
  DB/file-backed and safe.
- **Leaving SQLite** → `db.session.get_engine` refuses non-sqlite URLs deliberately;
  the sqlite-dialect upserts (`station_repo.resolve_datastream`,
  `station_repo.append_image`) must be ported first. Also: with WAL, a plain file copy
  of a live `control.db` is not a safe backup — use `sqlite3 .backup` or Litestream.



