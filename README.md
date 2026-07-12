# Eagleshot

Live monitoring dashboard for camera/sensor stations: a React frontend with a FastAPI backend that ingests HMAC-signed images and sensor readings from devices (e.g. OpenMV) and serves per-station pages with weather data.

## Frontend setup

The frontend is a Vite + React + TypeScript app. You need Node.js & npm ([install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)).

```sh
# Install dependencies
cd frontend
npm install

# Start the dev server (auto-reload; proxies /api to the backend)
npm run dev
```

The dev server reads `VITE_API_BASE_URL` and the ports from the root `.env` — see the Backend setup section below.

## Backend setup (FastAPI)

The backend is a single FastAPI service with two API surfaces: session-cookie frontend APIs and HMAC-signed device APIs for image/sensor ingestion.

### 1) Create the root `.env`

Create a single `.env` in the project root for both frontend and backend settings:

```env
# Frontend
VITE_API_BASE_URL=/api/v1

# Backend
OPENWEATHER_API_KEY=your_api_key_here
APP_AUTH_EMAIL=admin@example.com
APP_AUTH_PASSWORD=use_a_long_random_password_here
APP_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080

# Database: a local SQLite file is created automatically at <APP_DATA_DIR>/control.db.
# Set DATABASE_URL only to point at a different SQLAlchemy database.
# DATABASE_URL=sqlite:////absolute/path/to/control.db
```

A local SQLite database holds all metadata (stations, users, readings, image metadata); image blobs are written under `backend/data/`. It's created automatically on first run — no database server to set up. Set `DATABASE_URL` only if you want the data somewhere other than the default `<APP_DATA_DIR>/control.db`.
`VITE_API_BASE_URL` is read by the frontend from the root `.env`.
`OPENWEATHER_API_KEY` is required for the weather endpoints.
`APP_AUTH_EMAIL` and `APP_AUTH_PASSWORD` are used for browser/admin sessions only; do not put them in firmware.
`APP_AUTH_PASSWORD` must be at least 12 characters when auth is enabled.
`APP_CORS_ORIGINS` is required and should list the exact allowed frontend origins.
Brute-force protection, login throttling, and account lockout are not built into the application code.
Devices sign `/v1/ingest/stations/{station_id}/images` and `/v1/ingest/stations/{station_id}/data` with the per-station HMAC secret.
Plain HTTP cannot hide payload contents from someone who can inspect the network, so use it only on a trusted LAN or put the device API behind HTTPS, a VPN, or a private tunnel.

### 2) Install backend dependencies

```sh
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
```

### 3) Run the backend
```sh
# Activate the virtual environment
.venv\Scripts\activate

# Navigate to the backend directory if not already there
cd backend

# Start the FastAPI server with auto-reload and load the root .env
# (the SQLite schema + plan tiers are created automatically on startup)
uvicorn main:create_app --factory --reload --port 3000 --env-file ../.env
```

The backend needs no database server — control-plane data is a local SQLite file
under `backend/data/`, created on first run.

For the backend documentation, go to `http://localhost:3000/docs` in your browser.

### 4) Point the frontend to the backend (optional)

The frontend is configured to call the backend through `/api`, which works in local Vite dev and in Docker.
If you need to override that, set `VITE_API_BASE_URL` in the root `.env`:

```env
VITE_API_BASE_URL=/api/v1
```

## Docker Compose

The repo includes Dockerfiles for the frontend and backend plus a `docker-compose.yml` stack.

### Ports

- frontend: `http://localhost:8080`
- backend: `http://localhost:3000`
- frontend-to-backend browser traffic goes through `http://localhost:8080/api`

### 1) Edit the root env file

Update the root `.env` file and set the values you need, especially:

- `APP_AUTH_EMAIL`
- `APP_AUTH_PASSWORD`
- `OPENWEATHER_API_KEY` if you want live weather
- `CLOUDFLARE_TUNNEL_TOKEN` if you want the tunnel container

### 2) Start frontend and backend

```sh
docker compose up --build
```

### 3) Start Cloudflare Tunnel

```sh
docker compose --profile tunnel up --build
```

Set `CLOUDFLARE_TUNNEL_TOKEN` in the root `.env`. In the Cloudflare dashboard, configure the tunnel's **public hostnames** to point at Docker service names, not `localhost`:

- **App** `<your-domain>` -> `http://frontend:8080`
- **Device/ingest API** `api.<your-domain>` -> `http://backend:3000` — a dedicated hostname for devices, bypassing the frontend (matches the OpenMV client's `API_HOST`)

#### HTTP vs HTTPS for devices

Browsers must use HTTPS, but some devices (e.g. a cellular modem) can't do TLS. Device requests are HMAC-signed, so they're safe over plain HTTP. To force HTTPS for the app while still letting TLS-incapable devices reach the ingest hostname over plain HTTP:

1. **SSL/TLS → Edge Certificates → Always Use HTTPS: Off** (zone-wide). Universal SSL still serves HTTPS on every hostname, so capable devices keep using `https://api.<your-domain>`.
2. **Rules → Redirect Rules** → force HTTPS **only for the app**: `If http.host eq "<your-domain>" and not ssl → 301 to https://...`. The `api.<your-domain>` host has no redirect, so devices may use either scheme.
3. **Security → WAF** → add a skip/allow rule for `api.<your-domain>/v1/ingest/*` so device POSTs are never served a managed (JS) challenge they can't solve. A per-IP rate-limit rule there is optional.

In production also set `APP_REQUIRE_HTTPS=true` in the root `.env` (defense in depth: the backend then 426s plain-HTTP user routes while leaving `/v1/ingest/*` HTTP-allowed; it also flips the session cookie's `Secure` flag on). The backend runs uvicorn with `--proxy-headers`, so it honors Cloudflare's `X-Forwarded-Proto` — but only from the sources listed in `FORWARDED_ALLOW_IPS` (defaults to the pinned compose network subnet). **Never set `FORWARDED_ALLOW_IPS=*`**: that lets any client spoof `X-Forwarded-Proto`/`X-Forwarded-For` and bypass HTTPS enforcement and the per-IP login throttle. The compose file binds the backend's host port to `127.0.0.1` so it isn't internet-reachable; when using the tunnel you can drop the backend `ports:` mapping in `docker-compose.yml` entirely so only `cloudflared` can reach `backend:3000`.

## Tech stack

- **Frontend:** Vite, React, TypeScript, Tailwind CSS, shadcn-ui
- **Backend:** FastAPI (Python), SQLAlchemy + SQLite, uvicorn
- **Devices:** OpenMV (MicroPython) and a CPython client, with HMAC-signed image/sensor ingestion

## Device firmware

The canonical device firmware is the OpenMV (MicroPython) client at
[`clients/openmv/main.py`](clients/openmv/main.py): the cellular modem driver,
server clock sync, capture scheduling, and deep sleep. It is a single
self-contained file — HMAC request signing is inlined (pure-Python, no `hmac`
module needed) so there's nothing else to copy to the board. The same wire
format is implemented by the CPython client in [`clients/python/`](clients/python/).
Porting to other boards (ESP32-CAM, Raspberry Pi) is covered in
[`backend/README.md`](backend/README.md#porting-to-other-devices-esp32-cam-raspberry-pi-).

To provision a device: create the station, then `POST
/stations/<id>/rotate-device-secret` in the admin UI. Set `STATION_ID` in
`main.py` to the station's stable opaque `id` (the `id` field in the API, not the
display name or pretty URL slug) and paste the returned secret into
`STATION_SECRET_B64`. Copy `main.py` to the board (it's self-contained).
