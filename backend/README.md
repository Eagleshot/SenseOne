# Eagleshot backend

FastAPI service for station management, weather data, and device ingestion.

## Setup

Use Python 3.10 or newer. From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt
```

`requirements-dev.txt` includes runtime dependencies and the test runner.
Production installs should use `requirements.txt`.

Configuration is loaded from the project-root `.env`; copy `.env.example` and
set the values needed for your environment.

## Run

From `backend/`:

```powershell
python main.py
```

The default address is `http://127.0.0.1:3000`.

## API reference

The running service is the single source of truth for API contracts:

- Interactive documentation: `http://127.0.0.1:3000/docs`
- OpenAPI schema: `http://127.0.0.1:3000/openapi.json`

Use the configured backend host and port when they differ from the defaults.

## Device clients

Reference clients are available for [CPython](../clients/python/) and
[OpenMV/MicroPython](../clients/openmv/). Create a station in the application,
rotate its device secret, and configure the returned station id and secret in
the client. The request contract and authentication format are documented in
the API reference above.

## Mock data

From `backend/`:

```powershell
python .\seed\seed_mock_data.py --overwrite
```

See [seed/README.md](seed/README.md) for available options.
