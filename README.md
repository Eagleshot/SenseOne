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
VITE_API_BASE_URL=/api/v1

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
Devices sign `/v1/device/stations/{station_id}/images` and `/v1/device/stations/{station_id}/sensor-readings` with the per-station HMAC secret.
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

The frontend is configured to call the backend through `/api/v1`, which works in local Vite dev and in Docker.
If you need to override that, set `VITE_API_BASE_URL` in the root `.env`:

```env
VITE_API_BASE_URL=/api/v1
```

## Docker Compose

The repo includes Dockerfiles for the frontend and backend plus a `docker-compose.yml` stack.

### Ports

- frontend: `http://localhost:8080`
- backend: `http://localhost:3000`
- frontend-to-backend browser traffic goes through `http://localhost:8080/api/v1`

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
