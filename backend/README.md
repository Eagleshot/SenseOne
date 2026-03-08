# SenseOne Backend Tutorial

## Mock data seeding

From `backend/`:

```powershell
python .\seed_mock_data.py
```

This creates per-camera folders in `backend/data/<camera_id>/` with:

- `images/` mock assets
- `config.yaml`
- `camera.db` containing timeline rows

Use `--camera-id`, `--count`, and `--overwrite` to control generated sample data:

```powershell
python .\seed_mock_data.py --camera-id matterhorn-01 --count 24 --overwrite
```

This backend is a single FastAPI server that:

- accepts uploads on `POST /upload/{camera_id}` from the device
- serves the frontend API routes used by the Vite app
- saves uploaded files into `backend/data/<camera>/images/`, where each camera has its own folder
- creates a `config.yaml` and `camera.db` per camera directory on first write
- can optionally expose weather and auth features through `backend/.env`

## 1) Prerequisites

- Python 3.10+ (3.11+ recommended)
- `pip`
- One sample `.jpg` file for local testing

Optional for the frontend-auth and weather features:

- `backend/.env` with `APP_AUTH_USERNAME`, `APP_AUTH_PASSWORD`, and `OPENWEATHER_API_KEY`

## 2) Open the backend folder

```powershell
cd c:\Users\Noel\Desktop\SenseOne2\backend
```

## 3) Create and activate a virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

## 4) Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

## 5) Start the backend

From `backend/`:

```powershell
python .\main.py
```

Expected behavior:

- server starts on `0.0.0.0:3000`
- `backend/data/` is created automatically (if missing)
- `http://127.0.0.1:3000/docs` serves the OpenAPI docs

## 6) Test with a local image upload

```powershell
Invoke-WebRequest `
  -Method Post `
  -Uri "http://127.0.0.1:3000/upload/{CAMERA_ID}" `
  -Headers @{ "X-Filename" = "test.jpg" } `
  -ContentType "image/jpeg" `
  -InFile "C:\path\to\test.jpg"
```

You should get a response similar to:

```text
File uploaded as test.jpg
```

Then confirm file exists:

```powershell
Get-ChildItem .\data\<CAMERA_ID>\images
```

## 7) Connect your ESP32 camera firmware

Your firmware already matches this backend contract:

- `server_port` = `3000`
- `resource` = `"/upload/{camera_id}"`
- legacy fallback: `"/upload"` with required header `X-Camera-Id`
- request header `X-Filename`

These are defined in `config.h`.

Important:

- `server_ip` in `config.h` must point to the machine/IP running this backend.
- `127.0.0.1` will only work from the same machine, not from the ESP32.
- If needed, allow inbound TCP port `3000` in Windows Firewall.

Optional:

- set `APP_DATA_DIR` to override the data root.
- set `APP_DEFAULT_CAMERA_ID` to change the fallback camera id when none is provided.
- per-camera config endpoints:
- `GET /cameras/{camera_id}/config`
- `PUT /cameras/{camera_id}/config`

## 8) Troubleshooting

- `Connection to server failed!` on device:
  - verify `server_ip`
  - verify backend is running
  - verify port `3000` is open/reachable
- `404 Not Found`:
  - ensure firmware posts to `/upload/{camera_id}` (or `/upload` with `X-Camera-Id`)
- Empty/incorrect filename:
  - backend falls back to `default.jpg` when `X-Filename` is missing
- File not where expected:
- uploaded files are written to `backend/data/<camera>/images/`
