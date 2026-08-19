# Eagleshot

Live monitoring dashboard for camera and sensor stations. The project contains
a React frontend, a FastAPI backend, and reference device clients.

## Frontend setup

The frontend requires Node.js and npm.

```sh
cd frontend
npm install
npm run dev
```

The development server reads its settings from the project-root `.env` and
proxies `/api` to the backend.

## Backend setup

Create `.env` from [.env.example](.env.example), then install and run the
backend:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe main.py
```

`requirements-dev.txt` includes runtime dependencies and the test runner.
Production containers install `backend/requirements.txt` only.

The backend uses a local SQLite database by default and creates its data
directory on first run. A separate database server is not required.

## Backend API reference

The running FastAPI service is the single source of truth for backend API
contracts:

- Interactive documentation: `http://localhost:3000/docs`
- OpenAPI schema: `http://localhost:3000/openapi.json`

See [backend/README.md](backend/README.md) for backend setup and device-client
configuration. API endpoints, payloads, and authentication formats are kept in
FastAPI rather than duplicated here.

## Docker Compose

Start the frontend and backend:

```sh
docker compose up --build
```

Default addresses:

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:3000`

To include the optional Cloudflare Tunnel service, set
`CLOUDFLARE_TUNNEL_TOKEN` and run:

```sh
docker compose --profile tunnel up --build
```

Configure the tunnel hostnames to reach `frontend:8080` and `backend:3000`.

## Device clients

Reference clients are provided for [OpenMV/MicroPython](clients/openmv/) and
[CPython](clients/python/). Create a station in the application, rotate its
device secret, and configure the returned station id and secret in the client.
The HTTP contract is documented in the backend `/docs` page.

## Tech stack

- Frontend: Vite, React, TypeScript, Tailwind CSS, shadcn-ui
- Backend: FastAPI, SQLAlchemy, SQLite, uvicorn
- Devices: OpenMV/MicroPython and CPython reference clients
