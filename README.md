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

The backend is a single FastAPI service that powers the frontend APIs and the ESP32 image upload endpoint.

### 1) Create a backend `.env`

Create `backend/.env` if you want weather data and authenticated settings management:

```env
OPENWEATHER_API_KEY=your_api_key_here
APP_AUTH_USERNAME=your_admin_username
APP_AUTH_PASSWORD=use_a_long_random_password_here
APP_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

`OPENWEATHER_API_KEY` is required for the weather endpoints.
`APP_AUTH_USERNAME` and `APP_AUTH_PASSWORD` are required only if you want `/auth/*` and `/config`.
`APP_CORS_ORIGINS` defaults to local Vite origins in development and must be set in production.

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

# Start the FastAPI server with auto-reload
uvicorn main:app --reload --port 3000
```
If you created `backend/.env`, add `--env-file .env` to that command.

For the backend documentation, go to `http://localhost:3000/docs` in your browser.

### 4) Point the frontend to the backend (optional)

The frontend is configured to call the backend through `/api`, which works in local Vite dev and in Docker.
If you need to override that, set `VITE_API_BASE_URL` in `frontend/.env`:

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

### 3) Start Cloudflare Tunnel as well

```sh
docker compose --profile tunnel up --build
```

In the Cloudflare Zero Trust dashboard, point your public hostnames at the Docker service URLs:

- frontend hostname -> `http://frontend:8080`
- backend hostname -> `http://backend:3000` (optional)

### 4) Use a repo-managed Cloudflare config instead of dashboard ingress

The repo now includes `cloudflared/config.yml` with:

- `api.eagleshot.org` -> `http://backend:3000`
- `dashboard.eagleshot.org` -> `http://frontend:8080`

To use that config:

1. Put your tunnel credentials JSON at `cloudflared/credentials.json`
2. Edit `tunnel:` in `cloudflared/config.yml` to your real tunnel UUID
3. Start the config-driven profile:

```sh
docker compose --profile tunnel-config up --build -d
```

Use either `tunnel` or `tunnel-config`, not both at the same time.

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS




# SenseOne

// Settings:
// ESP32S3 Dev Module
// Tools -> USB CDC on Boot: "Enabled"
// Tools -> PSRAM: "QSPI PSRAM"
//
// SD card requirements (for this project):
// - Interface: SD_MMC (1-bit mode)
// - Pins: CLK=GPIO5, CMD=GPIO4, D0=GPIO6
// - Filesystem: FAT32 (MBR partition table)
// - Recommended allocation unit: 32KB
// - Avoid exFAT/NTFS for best compatibility with SD_MMC

// /home/eagleshot_drone/uploads/20251031_1529Z.jpg
/*Verison*/
//ESP32 Arduino 2.3.3
//TinyGSM 0.12.0

// TODOs:

// Timestamp uploaded images -> different time sources?
// Upload from SD card
// Check GPRS - at+cops=?
// Change modem speed - Serial1.println("AT+IPR=230400"); // TODO Change modem speed
// EEPROM for settings etc. - #include <EEPROM.h>
// Deep sleep/modem power down/power measurement
// Server to docker?
// Time sync internet/gps
// Domain instead of ip
// Save sensor data
// Remote firmware update
// Location and time - GPS und GSM
