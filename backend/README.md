# SenseOne Backend Tutorial

This backend is a single FastAPI server that:

- listens on `POST /upload` for raw image uploads from the device
- serves the frontend API routes used by the Vite app
- saves uploaded files into `backend/uploads/`
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
- `backend/uploads/` is created automatically (if missing)
- `http://127.0.0.1:3000/docs` serves the OpenAPI docs

## 6) Test with a local image upload

```powershell
Invoke-WebRequest `
  -Method Post `
  -Uri "http://127.0.0.1:3000/upload" `
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
Get-ChildItem .\uploads\
```

## 7) Connect your ESP32 camera firmware

Your firmware already matches this backend contract:

- `server_port` = `3000`
- `resource` = `"/upload"`
- request header `X-Filename`

These are defined in `config.h`.

Important:

- `server_ip` in `config.h` must point to the machine/IP running this backend.
- `127.0.0.1` will only work from the same machine, not from the ESP32.
- If needed, allow inbound TCP port `3000` in Windows Firewall.

## 8) Troubleshooting

- `Connection to server failed!` on device:
  - verify `server_ip`
  - verify backend is running
  - verify port `3000` is open/reachable
- `404 Not Found`:
  - ensure firmware posts to `/upload`
- Empty/incorrect filename:
  - backend falls back to `default.jpg` when `X-Filename` is missing
- File not where expected:
  - uploaded files are always written to `backend/uploads/`
