# SenseOne Backend Tutorial

## Mock data seeding

Seeds the **SQLite** control plane (the seeder creates the schema + plans itself —
see [`seed/README.md`](seed/README.md)). From `backend/`:

```powershell
python .\seed\seed_mock_data.py --overwrite
```

It inserts users/stations/sensor_readings/station_images rows and writes
timeline image blobs under `backend/data/<slug>/images/`. Use `--station-id`,
`--count`, and `--overwrite` to control the generated sample data.

This backend is a single FastAPI server that:

- serves the frontend API routes used by the Vite app with session-cookie auth
- accepts HMAC-signed device uploads on `POST /v1/ingest/stations/{station_id}/images` and `POST /v1/ingest/stations/{station_id}/data` — see [Device auth (HMAC)](#device-auth-hmac)
- stores all station metadata, ownership, sensor readings, and image metadata in a local **SQLite** database
- writes uploaded image blobs to `backend/data/<station>/images/`
- exposes weather and auth features through the shared project root `.env`

## 1) Prerequisites

- Python 3.10+ (3.11+ recommended)
- `pip`
- No database server — control-plane data is a local SQLite file
  (`backend/data/control.db`), created automatically on first run.
- One sample `.jpg` file for local testing

Required/optional in the shared frontend/backend `.env`:

- `DATABASE_URL` — optional; only set it to point at a different SQLAlchemy database (defaults to `sqlite:///<APP_DATA_DIR>/control.db`)
- `VITE_API_BASE_URL` for the frontend
- `APP_AUTH_EMAIL`, `APP_AUTH_PASSWORD`, and `OPENWEATHER_API_KEY` for the backend
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
| `X-Station-Id` | `7f3a9c2b1e08` | The station's stable opaque `id` (its `id` in the API, not the display name or pretty URL slug). Must match the URL path. |
| `X-Timestamp` | `1748000000` | Unix seconds, within +-300 s of the server clock. |
| `X-Nonce` | `0123456789abcdef0123456789abcdef` | Hex, >=16 chars, fresh per request. |
| `X-Signature` | `v1=<64 hex chars>` | HMAC-SHA256 of the canonical string with the per-station secret. |

Provision the per-station secret from an authenticated admin session:

```
POST /v1/stations/{station_id}/rotate-device-secret
```

The response includes the base64url secret exactly once — flash it to the device and discard the response.

Reference signers:

- Python: [`clients/python/eagleshot.py`](../clients/python/eagleshot.py)
- MicroPython / OpenMV: the signer is inlined in [`clients/openmv/main.py`](../clients/openmv/main.py) (single self-contained file to flash)

Devices without an RTC can call the unauthenticated `GET /clock` once at boot and track the offset against a monotonic counter.

### Porting to other devices (ESP32-CAM, Raspberry Pi, …)

Any device that can issue an HTTP request and compute HMAC-SHA256 can push to the same endpoints — the API is device- and transport-agnostic. To port a new board:

1. **Sign the request** exactly as in the table above (canonical string + four headers; see `station_hmac.py`). Reuse a shared signer where you can:
   - **Raspberry Pi / any CPython host** — `import eagleshot` from [`clients/python/eagleshot.py`](../clients/python/eagleshot.py) and POST with `requests` (see steps 6–7). Works over WiFi, Ethernet, or cellular; no board-specific firmware needed.
   - **OpenMV / MicroPython** — start from [`clients/openmv/main.py`](../clients/openmv/main.py), which inlines a pure-Python `sign_request` (no `hmac` module needed); it's a single self-contained file to flash to the board.
   - **ESP32-CAM (Arduino/C++)** — there's no shared lib for C++, so reimplement the signer with mbedTLS (bundled in arduino-esp32): SHA-256 the JPEG framebuffer (`mbedtls_sha256`), build the same `\n`-joined canonical string, HMAC it with `mbedtls_md_hmac` (`MBEDTLS_MD_SHA256`), hex-encode lowercase, and send via `HTTPClient`. **Mind the secret encoding:** it's base64**url** and routinely contains `-`/`_`, so translate `-`→`+`, `_`→`/` and re-pad before `mbedtls_base64_decode`. Validate against the known-answer vector below before touching hardware.
2. **Pick the transport** (see *Transport / TLS* below): prefer HTTPS where the board supports it; fall back to plain HTTP only where it can't.
3. **Honor the upload contract:**
   - `X-Filename` is optional: when supplied it must be `YYYYMMDD_HHMMZ_<camera>.jpg` (UTC capture minute) and becomes the stored capture timestamp; when omitted the server stamps a default name from the current UTC minute. **It is folded into the HMAC signature** (it sets the stored capture time/stream, so it must not be tamperable); requests that omit it sign an empty string for that line.
   - `Content-Type` `image/jpeg|png|webp`; the body must be a real image (the server sniffs the bytes).
   - Default size cap 25 MB (`APP_MAX_UPLOAD_BYTES`).
   - `X-Timestamp` must be within ±300 s of the server clock; RTC-less boards sync via `GET /clock` as above.
4. **Sensor readings are free-form:** any JSON keys beyond `timestamp` / `nextStart` are stored verbatim, so a new board can report whatever metrics it has (battery, soil moisture, …) with no server-side change.

**Known-answer vector** — validate any new signer against this exact input before testing on hardware (generated by `tests/_signing.py`, the server's own reference):

```
secret_b64 = abcdef0123456789-_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA   # base64url: note the - and _
station_id = silvretta-glacier
method     = POST
path       = /v1/ingest/stations/silvretta-glacier/images
body       = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
timestamp  = 1748000000
nonce      = 0123456789abcdef0123456789abcdef
x_filename = 20260524_1430Z_front.jpg   # signed (8th canonical line); "" when omitted

sha256(body) = 03f2833d8de9b8473d2afa2d09d180a5ebe9144de756a480b24e2b6aee17d0ec
X-Signature  = v1=41b58876208d0fca3bc532bd1c1c1084019f9f43740c214455585c4af2115faf
```

#### Transport / TLS

The shared secret is only ever an HMAC key — it never goes over the wire — so a signed request is safe to send over **plain HTTP**: an on-path observer can read a (public) webcam frame but cannot forge, tamper with, or replay it, nor recover the secret. Use plain HTTP only for links that genuinely can't do TLS (e.g. a cellular modem). Capable boards (Raspberry Pi, ESP32) should use **HTTPS** to the ingest hostname and lose nothing — a Raspberry Pi validates Cloudflare's certificate; an ESP32 can bundle Cloudflare's root CA or, at minimum, use `client.setInsecure()` (still encrypted; the HMAC covers authenticity). Configuring Cloudflare to allow both is covered in the root `README.md` ("Start Cloudflare Tunnel").

## 6) Test with a local image upload

```powershell
python - <<'PY'
import sys
sys.path.insert(0, "../clients/python")
import eagleshot, requests

STATION_ID = "{STATION_ID}"
SECRET_B64 = "{DEVICE_SECRET_B64}"
body = open(r"C:\path\to\test.jpg", "rb").read()
path = f"/v1/ingest/stations/{STATION_ID}/images"

headers = eagleshot.sign_request(
    station_id=STATION_ID,
    secret_b64=SECRET_B64,
    method="POST",
    path=path,
    body=body,
    x_filename="20260524_1430Z_front.jpg",  # signed; returned as the X-Filename header
)
headers["Content-Type"] = "image/jpeg"

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
import eagleshot, requests

STATION_ID = "{STATION_ID}"
SECRET_B64 = "{DEVICE_SECRET_B64}"
path = f"/v1/ingest/stations/{STATION_ID}/data"
body = json.dumps({
    "timestamp": "2026-05-24T14:30:00Z",
    "firmwareVersion": "openmv-n6-2026.05",
    "nextStart": "2026-05-24T15:00:00Z",
    "wakeReason": "timer",
    "voltage": 3.9,
}).encode("utf-8")

headers = eagleshot.sign_request(
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

For the OpenMV flow, `timestamp` is the adjusted UTC image capture minute and should match the `YYYYMMDD_HHMMZ` prefix in `X-Filename`. Weather-like fields are optional; log fields such as `firmwareVersion`, `nextStart`, `wakeReason`, `voltage`, and `deviceTemperature` can be sent sparsely.

## 8) Endpoints

The public HTTP API is versioned under `/v1` (app routes at `/v1/...`, device
ingestion at `/v1/ingest/...`). Only the unversioned infrastructure endpoints
(`/`, `/health`, `/clock`, `/favicon.ico`) live at the root.

Frontend routes (session-cookie auth):

- `GET /v1/stations`
- `GET /v1/stations/{station_id}`
- `GET /v1/stations/{station_id}/data`
- `GET /v1/stations/{station_id}/image-captures`
- `GET /v1/stations/{station_id}/weather/current`
- `GET /v1/stations/{station_id}/weather/forecast`
- `GET /v1/stations/{station_id}/config`
- `PUT /v1/stations/{station_id}/config`
- `POST /v1/stations/{station_id}/rotate-device-secret`

Ingest routes (device push/pull, HMAC signing — see above):

- `POST /v1/ingest/stations/{station_id}/images`
- `POST /v1/ingest/stations/{station_id}/data`
- `GET /v1/ingest/stations/{station_id}/config`

Open:

- `GET /clock`
- `GET /health`

## 9) Troubleshooting

- `401 Unauthorized` on a device request:
  - timestamp is outside the +-300 s window — re-sync via `GET /clock`
  - nonce was reused — generate a fresh one per request
  - secret on device doesn't match the server — rotate via `POST /stations/{station_id}/rotate-device-secret` and re-flash
- `404 Not Found`:
  - station id doesn't exist or the URL path doesn't match `/v1/ingest/stations/{station_id}/images` / `.../data` / `.../config`
- `422 Unprocessable Entity` on image upload:
  - a *supplied* `X-Filename` must be a real UTC capture name such as `20260524_1430Z_front.jpg` (omit it to have the server stamp one)
- `413 Payload Too Large`:
  - default upload cap is 25 MB; override with `APP_MAX_UPLOAD_BYTES`
- `426 Upgrade Required`:
  - `APP_REQUIRE_HTTPS=true` is set but the request reached the server over plain HTTP — fix the reverse proxy / `--proxy-headers` setup, or scope the env flag to production only
- File not where expected:
  - uploaded files are written to `backend/data/<station>/images/`
