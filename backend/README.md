# SenseOne Backend Tutorial

## Mock data seeding

From `backend/`:

```powershell
python .\seed\seed_mock_data.py
```

This creates per-station folders in `backend/data/<station_id>/` with:

- `images/` mock assets
- `config.yaml` including schedule and metadata (`title`, `lat`, `lon`, `alt`, `location`, `country`, `country_emoji`)
- `station.db` containing image capture and sensor reading rows

Use `--station-id`, `--count`, and `--overwrite` to control generated sample data:

```powershell
python .\seed\seed_mock_data.py --station-id matterhorn-01 --count 24 --overwrite
```

This backend is a single FastAPI server that:

- serves the frontend API routes used by the Vite app with session-cookie auth
- accepts HMAC-signed device uploads on `POST /device/stations/{station_id}/images` and `POST /device/stations/{station_id}/sensor-readings` — see [Device auth (HMAC)](#device-auth-hmac)
- saves uploaded files into `backend/data/<station>/images/`, where each station has its own folder
- creates a `config.yaml` and `station.db` per station directory on first write
- can optionally expose weather and auth features through the shared project root `.env`

## 1) Prerequisites

- Python 3.10+ (3.11+ recommended)
- `pip`
- One sample `.jpg` file for local testing

Optional for the shared frontend/backend `.env`:

- `VITE_API_BASE_URL` for the frontend
- `APP_AUTH_USERNAME`, `APP_AUTH_PASSWORD`, and `OPENWEATHER_API_KEY` for the backend
- `APP_REQUIRE_HTTPS=true` to reject plain-HTTP requests for user-auth routes (device routes stay HTTP-allowed since their auth is HMAC-signed)

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
python main.py
```

This reads `BACKEND_PORT` (and the rest of the config) from `..\.env`, defaulting to `3000` if unset. To override for a single run, set the env var first, e.g. `$env:BACKEND_PORT=4000; python main.py`.

Expected behavior:

- server starts on `0.0.0.0:<BACKEND_PORT>` (default `3000`)
- `backend/data/` is created automatically (if missing)
- `http://127.0.0.1:3000/docs` serves the OpenAPI docs (use your `BACKEND_PORT` if you changed it)

## Device auth (HMAC)

Devices authenticate every request by signing it — the shared secret never goes over the wire. See `backend/station_hmac.py` for the canonical signing string. Each request must carry these four headers:

| Header | Example | Notes |
| --- | --- | --- |
| `X-Station-Id` | `silvretta-glacier` | Must match the URL path. |
| `X-Timestamp` | `1748000000` | Unix seconds, within +-300 s of the server clock. |
| `X-Nonce` | `0123456789abcdef0123456789abcdef` | Hex, >=16 chars, fresh per request. |
| `X-Signature` | `v1=<64 hex chars>` | HMAC-SHA256 of the canonical string with the per-station secret. |

Provision the per-station secret from an authenticated admin session:

```
POST /stations/{station_id}/rotate-device-secret
```

The response includes the base64url secret exactly once — flash it to the device and discard the response.

Reference signers:

- Python: [`clients/python/eagleshot_signing.py`](../clients/python/eagleshot_signing.py)
- MicroPython / OpenMV: [`clients/openmv/eagleshot_signing.py`](../clients/openmv/eagleshot_signing.py)

Devices without an RTC can call the unauthenticated `GET /clock` once at boot and track the offset against a monotonic counter.

## 6) Test with a local image upload

```powershell
python - <<'PY'
import sys
sys.path.insert(0, "../clients/python")
import eagleshot_signing, requests

STATION_ID = "{STATION_ID}"
SECRET_B64 = "{DEVICE_SECRET_B64}"
body = open(r"C:\path\to\test.jpg", "rb").read()
path = f"/device/stations/{STATION_ID}/images"

headers = eagleshot_signing.sign_request(
    station_id=STATION_ID,
    secret_b64=SECRET_B64,
    method="POST",
    path=path,
    body=body,
)
headers.update({"Content-Type": "image/jpeg", "X-Filename": "20260524_1430Z_front.jpg"})

response = requests.post(f"http://127.0.0.1:3000{path}", data=body, headers=headers)
print(response.status_code, response.text)
PY
```

Expected response:

```json
{
  "filename": "20260524_1430Z_front.jpg",
  "url": "/stations/{STATION_ID}/images/20260524_1430Z_front.jpg"
}
```

Then confirm the file exists:

```powershell
Get-ChildItem .\data\<STATION_ID>\images
```

## 7) Test with a local sensor reading

```powershell
python - <<'PY'
import json, sys
sys.path.insert(0, "../clients/python")
import eagleshot_signing, requests

STATION_ID = "{STATION_ID}"
SECRET_B64 = "{DEVICE_SECRET_B64}"
path = f"/device/stations/{STATION_ID}/sensor-readings"
body = json.dumps({
    "timestamp": "2026-05-24T14:30:00Z",
    "firmwareVersion": "openmv-n6-2026.05",
    "nextStart": "2026-05-24T15:00:00Z",
    "cameraName": "front",
    "wakeReason": "timer",
    "voltage": 3.9,
}).encode("utf-8")

headers = eagleshot_signing.sign_request(
    station_id=STATION_ID,
    secret_b64=SECRET_B64,
    method="POST",
    path=path,
    body=body,
)
headers["Content-Type"] = "application/json"

response = requests.post(f"http://127.0.0.1:3000{path}", data=body, headers=headers)
print(response.status_code, response.text)
PY
```

For the OpenMV flow, `timestamp` is the adjusted UTC image capture minute and should match the `YYYYMMDD_HHMMZ` prefix in `X-Filename`. Weather-like fields are optional; log fields such as `firmwareVersion`, `nextStart`, `cameraName`, `wakeReason`, `voltage`, and `deviceTemperature` can be sent sparsely.

## 8) Endpoints

Frontend routes (session-cookie auth):

- `GET /stations`
- `GET /stations/{station_id}`
- `GET /stations/{station_id}/sensor-readings`
- `GET /stations/{station_id}/image-captures`
- `GET /stations/{station_id}/weather/current`
- `GET /stations/{station_id}/weather/forecast`
- `GET /stations/{station_id}/config`
- `PUT /stations/{station_id}/config`
- `POST /stations/{station_id}/rotate-device-secret`

Device routes (HMAC signing, see above):

- `POST /device/stations/{station_id}/images`
- `POST /device/stations/{station_id}/sensor-readings`
- `GET /device/stations/{station_id}/config`

Open:

- `GET /clock`
- `GET /health`

## 9) Troubleshooting

- `401 Unauthorized` on a device request:
  - timestamp is outside the +-300 s window — re-sync via `GET /clock`
  - nonce was reused — generate a fresh one per request
  - secret on device doesn't match the server — rotate via `POST /stations/{station_id}/rotate-device-secret` and re-flash
- `404 Not Found`:
  - station id doesn't exist or the URL path doesn't match `/device/stations/{station_id}/images` / `.../sensor-readings` / `.../config`
- `422 Unprocessable Entity` on image upload:
  - `X-Filename` must be a real UTC capture name such as `20260524_1430Z_front.jpg`
- `413 Payload Too Large`:
  - default upload cap is 25 MB; override with `APP_MAX_UPLOAD_BYTES`
- `426 Upgrade Required`:
  - `APP_REQUIRE_HTTPS=true` is set but the request reached the server over plain HTTP — fix the reverse proxy / `--proxy-headers` setup, or scope the env flag to production only
- File not where expected:
  - uploaded files are written to `backend/data/<station>/images/`
