# Welcome to your project

## Project info

# TODO

## How can I edit this code?

There are several ways of editing your application.

**Use your preferred IDE**

If you want to work locally using your own IDE, you can clone this repo and push changes. Pushed changes will also be reflected in Lovable.

The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

Follow these steps:

```sh
# Step 1: Clone the repository using the project's Git URL.
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory.
cd <YOUR_PROJECT_NAME>

# Step 3: Install the necessary dependencies.
npm i

# Step 4: Start the development server with auto-reloading and an instant preview.
npm run dev
```

## Backend setup (FastAPI)

The backend is a single FastAPI service with two API surfaces: session-cookie frontend APIs and HMAC-signed device APIs for image/sensor ingestion.

### 1) Create the root `.env`

Create a single `.env` in the project root for both frontend and backend settings:

```env
# Frontend
VITE_API_BASE_URL=/api

# Backend
OPENWEATHER_API_KEY=your_api_key_here
APP_AUTH_USERNAME=your_admin_username
APP_AUTH_PASSWORD=use_a_long_random_password_here
APP_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

`VITE_API_BASE_URL` is read by the frontend from the root `.env`.
`OPENWEATHER_API_KEY` is required for the weather endpoints.
`APP_AUTH_USERNAME` and `APP_AUTH_PASSWORD` are used for browser/admin sessions only; do not put them in firmware.
`APP_AUTH_PASSWORD` must be at least 12 characters when auth is enabled.
`APP_CORS_ORIGINS` is required and should list the exact allowed frontend origins.
Brute-force protection, login throttling, and account lockout are not built into the application code.
Devices sign `/device/stations/{station_id}/images` and `/device/stations/{station_id}/sensor-readings` with the per-station HMAC secret.
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
uvicorn main:create_app --factory --reload --port 3000 --env-file ../.env
```

For the backend documentation, go to `http://localhost:3000/docs` in your browser.

### 4) Point the frontend to the backend (optional)

The frontend is configured to call the backend through `/api`, which works in local Vite dev and in Docker.
If you need to override that, set `VITE_API_BASE_URL` in the root `.env`:

```env
VITE_API_BASE_URL=/api
```

## Docker Compose

The repo includes Dockerfiles for the frontend and backend plus a `docker-compose.yml` stack.

### Ports

- frontend: `http://localhost:8080`
- backend: `http://localhost:3000`
- frontend-to-backend browser traffic goes through `http://localhost:8080/api`

### 1) Edit the root env file

Update the root `.env` file and set the values you need, especially:

- `APP_AUTH_USERNAME`
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

Set `CLOUDFLARE_TUNNEL_TOKEN` in the root `.env`, then configure the Cloudflare dashboard public hostnames to point at Docker service names, not `localhost`:

- backend hostname -> `http://backend:3000`
- frontend hostname -> `http://frontend:8080`

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS




## Device firmware

The canonical device firmware is the OpenMV (MicroPython) client at
[`clients/openmv/main.py`](clients/openmv/main.py). It is a single file that
handles HMAC request signing, the cellular modem driver, server clock sync,
capture scheduling, and deep sleep.

To provision a device: create the station, then `POST
/stations/<id>/rotate-device-secret` in the admin UI and paste the returned
secret into `STATION_SECRET_B64` in `main.py`. Copy `main.py` to the board.
