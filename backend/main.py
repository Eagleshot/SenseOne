from __future__ import annotations

import sqlite3
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

try:
    from .mock_data import TIMEZONES, generate_historical_data, get_webcams
except ImportError:
    from mock_data import TIMEZONES, generate_historical_data, get_webcams


def parse_positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than 0.")
    return parsed


def parse_cors_origins() -> list[str]:
    raw_value = (os.getenv("APP_CORS_ORIGINS") or "").strip()
    if raw_value:
        origins = [origin.strip().rstrip("/") for origin in raw_value.split(",") if origin.strip()]
        if not origins:
            raise RuntimeError("APP_CORS_ORIGINS is set but empty.")
        if "*" in origins:
            raise RuntimeError("Wildcard CORS origins are not allowed.")
        return origins
    if IS_PRODUCTION:
        raise RuntimeError("APP_CORS_ORIGINS must be set in production.")
    return [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _sanitize_filename(raw_name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9.\-_]", "_", raw_name)
    return cleaned or "default.jpg"


def _sanitize_camera_id(raw_name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", raw_name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "camera"


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
EMBEDDED_FILENAME_TIMESTAMP_PATTERN = re.compile(r"(\d{8})_(\d{4})Z")


def _normalize_content_type(raw_content_type: str | None) -> str | None:
    if not raw_content_type:
        return None
    return raw_content_type.split(";", 1)[0].strip().lower()


def _media_type_from_path(path: Path) -> str | None:
    extension_to_media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    media_type = extension_to_media_type.get(path.suffix.lower())
    if media_type:
        return media_type
    try:
        header = path.read_bytes()[:16]
    except OSError:
        return None
    if header.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1A\n"):
        return "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _parse_embedded_timestamp(filename: str) -> datetime | None:
    match = EMBEDDED_FILENAME_TIMESTAMP_PATTERN.search(filename)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_supported_image_upload(filename: str, content_type: str | None) -> bool:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension_supported = False
    else:
        extension_supported = True

    normalized_content_type = _normalize_content_type(content_type)
    if normalized_content_type and not normalized_content_type.startswith("image/"):
        return False
    if not normalized_content_type:
        return extension_supported or extension == ""
    if normalized_content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        return False
    return extension_supported or extension == ""


def _normalize_camera_id(raw_camera_id: str | None) -> str:
    return _sanitize_camera_id(raw_camera_id or DEFAULT_CAMERA_ID)


def _camera_dir(camera_id: str) -> Path:
    return DATA_DIR / camera_id


def _camera_db_path(camera_id: str) -> Path:
    return _camera_dir(camera_id) / CAMERA_DB_FILENAME


def _camera_config_path(camera_id: str) -> Path:
    return _camera_dir(camera_id) / CAMERA_CONFIG_FILENAME


def _camera_config_yaml(camera_id: str) -> str:
    return _camera_config_yaml_for_values(camera_id, CONFIG)


def _camera_config_yaml_for_values(camera_id: str, values: AppConfig) -> str:
    return "\n".join(
        [
            f"camera_id: {camera_id}",
            f"camera_start_time: \"{values.camera_start_time}\"",
            f"camera_stop_time: \"{values.camera_stop_time}\"",
            f"use_sunrise_sunset: {'true' if values.use_sunrise_sunset else 'false'}",
            f"capture_interval_minutes: {values.capture_interval_minutes}",
            "",
        ]
    )


def _read_camera_config(camera_id: str) -> AppConfig:
    config_path = _camera_config_path(camera_id)
    if not config_path.exists():
        _ensure_camera_dir(camera_id)
        return AppConfig()

    try:
        text = config_path.read_text(encoding="utf-8")
        parsed: dict[str, object] = {}
        for line in text.splitlines():
            raw_line = line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue
            if ":" not in raw_line:
                continue
            key, raw_value = (part.strip() for part in raw_line.split(":", 1))
            value = raw_value.strip().strip("\"'")
            if key == "camera_id":
                continue
            if key in {"camera_start_time", "camera_stop_time"}:
                parsed[key] = value
            elif key == "use_sunrise_sunset":
                parsed[key] = value.lower() in {"1", "true", "yes", "on"}
            elif key == "capture_interval_minutes":
                parsed[key] = int(value)
        return AppConfig(**parsed)
    except (OSError, ValueError, TypeError) as exc:
        logging.warning("Failed to read camera config for %s: %s", camera_id, exc)
        return AppConfig()


def _write_camera_config(camera_id: str, values: AppConfig) -> None:
    _ensure_camera_dir(camera_id)
    _camera_config_path(camera_id).write_text(
        _camera_config_yaml_for_values(camera_id, values),
        encoding="utf-8",
    )


def _ensure_camera_dir(camera_id: str) -> None:
    camera_root = _camera_dir(camera_id)
    images_dir = camera_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    config_file = _camera_config_path(camera_id)
    if not config_file.exists():
        config_file.write_text(_camera_config_yaml(camera_id), encoding="utf-8")

    db_path = _camera_db_path(camera_id)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS camera_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


async def _store_uploaded_image(
    camera_id: str,
    filename: str,
    request: Request,
    content_type: str | None,
) -> tuple[str, str]:
    if not _is_supported_image_upload(filename, content_type):
        supported = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type. Allowed extensions: {supported}",
        )

    _ensure_camera_dir(camera_id)
    camera_root = _camera_dir(camera_id)
    images_dir = camera_root / "images"
    timestamp_ms = int(time.time() * 1000)
    stored_filename = f"{timestamp_ms}-{filename}"
    file_path = images_dir / stored_filename
    size_bytes = 0

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_value = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            ) from exc
        if content_length_value > APP_MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload too large. Maximum is {APP_MAX_UPLOAD_BYTES} bytes.",
            )

    with file_path.open("wb") as target:
        try:
            async for chunk in request.stream():
                if not chunk:
                    continue
                size_bytes += len(chunk)
                if size_bytes > APP_MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload too large. Maximum is {APP_MAX_UPLOAD_BYTES} bytes.",
                    )
                target.write(chunk)
        except HTTPException:
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            raise

    db_path = _camera_db_path(camera_id)
    captured_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO camera_images (filename, content_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (stored_filename, content_type or "", size_bytes, captured_at),
        )
        connection.commit()

    return stored_filename, f"/images/{camera_id}/images/{stored_filename}"


def _timeline_from_camera_db(camera_id: str, count: int) -> list[dict[str, str]] | None:
    db_path = _camera_db_path(camera_id)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT filename, created_at
                FROM camera_images
                """,
            ).fetchall()
    except sqlite3.Error as exc:
        logging.warning("Failed to read camera timeline for %s: %s", camera_id, exc)
        return None

    if not rows:
        return None

    timeline_items: list[tuple[datetime, bool, dict[str, str]]] = []
    images_dir = _camera_dir(camera_id) / "images"
    for row in rows:
        filename = row["filename"]
        image_path = images_dir / filename
        if not image_path.is_file():
            continue
        embedded_timestamp = _parse_embedded_timestamp(filename)
        timestamp = embedded_timestamp or _parse_iso_timestamp(row["created_at"]) or datetime.fromtimestamp(
            image_path.stat().st_mtime, timezone.utc
        )
        timeline_items.append(
            (
                timestamp,
                embedded_timestamp is not None,
                {
                    "timestamp": _iso_utc(timestamp),
                    "url": f"/images/{camera_id}/images/{filename}",
                },
            )
        )
    if not timeline_items:
        return None
    if any(item[1] for item in timeline_items):
        timeline_items = [item for item in timeline_items if item[1]]
    timeline_items.sort(key=lambda item: item[0])
    if len(timeline_items) > count:
        timeline_items = timeline_items[-count:]
    return [item[2] for item in timeline_items]


def _timeline_from_image_dir(camera_id: str, count: int) -> list[dict[str, str]]:
    images_dir = _camera_dir(camera_id) / "images"
    if not images_dir.exists():
        return []

    files = [path for path in images_dir.iterdir() if path.is_file()]
    if not files:
        return []

    timeline_items: list[tuple[datetime, bool, dict[str, str]]] = []
    for path in files:
        embedded_timestamp = _parse_embedded_timestamp(path.name)
        timestamp = embedded_timestamp or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        timeline_items.append(
            (
                timestamp,
                embedded_timestamp is not None,
                {
                    "timestamp": _iso_utc(timestamp),
                    "url": f"/images/{camera_id}/images/{path.name}",
                },
            )
        )
    if any(item[1] for item in timeline_items):
        timeline_items = [item for item in timeline_items if item[1]]
    timeline_items.sort(key=lambda item: item[0])
    if len(timeline_items) > count:
        timeline_items = timeline_items[-count:]
    return [item[2] for item in timeline_items]


def _latest_camera_image_url(camera_id: str) -> str | None:
    timeline = _timeline_from_image_dir(camera_id, count=1)
    if not timeline:
        return None
    return timeline[-1]["url"]


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}

AUTH_USERNAME = (os.getenv("APP_AUTH_USERNAME") or "").strip()
AUTH_PASSWORD = (os.getenv("APP_AUTH_PASSWORD") or "").strip()
if bool(AUTH_USERNAME) != bool(AUTH_PASSWORD):
    raise RuntimeError("APP_AUTH_USERNAME and APP_AUTH_PASSWORD must either both be set or both be unset.")
AUTH_ENABLED = bool(AUTH_USERNAME and AUTH_PASSWORD)
if AUTH_ENABLED and IS_PRODUCTION and len(AUTH_PASSWORD) < 12:
    raise RuntimeError("APP_AUTH_PASSWORD must be at least 12 characters in production.")

AUTH_TOKEN_TTL_SECONDS = parse_positive_int_env("APP_AUTH_TOKEN_TTL_SECONDS", 43200)
AUTH_COOKIE_NAME = "eagleshot_session"
AUTH_COOKIE_SECURE = IS_PRODUCTION
AUTH_COOKIE_SAMESITE = "strict"

APP_CORS_ORIGINS = parse_cors_origins()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
APP_MAX_UPLOAD_BYTES = parse_positive_int_env("APP_MAX_UPLOAD_BYTES", 25 * 1024 * 1024)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR") or (BASE_DIR / "data")).resolve()
DEFAULT_CAMERA_ID = (os.getenv("APP_DEFAULT_CAMERA_ID") or "default").strip() or "default"
CAMERA_DB_FILENAME = "camera.db"
CAMERA_CONFIG_FILENAME = "config.yaml"

DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
if not AUTH_ENABLED:
    logging.warning("Authentication is disabled because APP_AUTH_USERNAME/APP_AUTH_PASSWORD are not set.")

app = FastAPI(title="Eagleshot API", version="0.1.0")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["X-Download-Options"] = "noopen"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), usb=()"

    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

    return response


@app.get("/images/{camera_id}/images/{filename}")
def get_camera_image(
    camera_id: str,
    filename: str,
) -> FileResponse:
    normalized_camera_id = _normalize_camera_id(camera_id)
    if camera_id != normalized_camera_id:
        raise HTTPException(status_code=400, detail="Invalid camera id.")
    if filename != _sanitize_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    image_path = DATA_DIR / normalized_camera_id / "images" / filename
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(image_path, media_type=_media_type_from_path(image_path))

app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Filename", "X-Camera-Id"],
)


class AppConfig(BaseModel):
    camera_start_time: str = Field(default="06:00")
    camera_stop_time: str = Field(default="20:00")
    use_sunrise_sunset: bool = False
    capture_interval_minutes: int = Field(default=30, ge=1, le=1440)

    @field_validator("camera_start_time", "camera_stop_time")
    @classmethod
    def validate_time_field(cls, value: str) -> str:
        candidate = value.strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", candidate):
            raise ValueError("Time must be in HH:MM (24-hour) format.")
        return candidate


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    expires_in: int
    username: str


class MeResponse(BaseModel):
    username: str


CONFIG = AppConfig()
AUTH_SESSIONS: dict[str, tuple[str, float]] = {}
bearer_scheme = HTTPBearer(auto_error=False)


def ensure_auth_configured() -> None:
    if AUTH_ENABLED:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured.",
    )


def create_session(username: str) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + AUTH_TOKEN_TTL_SECONDS
    AUTH_SESSIONS[token] = (username, expires_at)
    return token, AUTH_TOKEN_TTL_SECONDS


def prune_expired_sessions() -> None:
    now = time.time()
    expired_tokens = [token for token, (_, expires_at) in AUTH_SESSIONS.items() if expires_at <= now]
    for token in expired_tokens:
        AUTH_SESSIONS.pop(token, None)


def resolve_session_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


def get_current_username(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    ensure_auth_configured()
    prune_expired_sessions()

    token = resolve_session_token(request, credentials)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    session = AUTH_SESSIONS.get(token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

    username, expires_at = session
    if expires_at <= time.time():
        AUTH_SESSIONS.pop(token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

    return username


async def fetch_openweather(endpoint: str, lat: float, lon: float, units: str = "metric") -> dict:
    if not OPENWEATHER_API_KEY:
        raise HTTPException(status_code=500, detail="Missing OPENWEATHER_API_KEY.")
    url = f"https://api.openweathermap.org/data/2.5/{endpoint}"
    params = {"lat": lat, "lon": lon, "units": units, "appid": OPENWEATHER_API_KEY}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail="OpenWeather request failed.")
    return response.json()


@app.get("/")
def root() -> dict:
    return {"name": "Eagleshot API", "status": "ok"}


@app.get("/health", response_class=PlainTextResponse)
def health() -> PlainTextResponse:
    return PlainTextResponse("OK")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/upload", response_class=PlainTextResponse)
async def upload_image(
    request: Request,
    x_camera_id: Optional[str] = Header(default=None, alias="X-Camera-Id"),
    webcam_id: Optional[str] = Query(default=None),
    x_filename: Optional[str] = Header(default=None),
    _: str = Depends(get_current_username),
) -> PlainTextResponse:
    if not x_camera_id and not webcam_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="camera id is required via X-Camera-Id header or webcam_id query parameter",
        )
    camera_id = _normalize_camera_id(x_camera_id or webcam_id)
    filename = _sanitize_filename(x_filename or "default.jpg")
    stored_filename, _ = await _store_uploaded_image(
        camera_id=camera_id,
        filename=filename,
        request=request,
        content_type=request.headers.get("content-type"),
    )
    logging.info("File saved for camera %s as %s", camera_id, stored_filename)
    return PlainTextResponse(f"File uploaded as {stored_filename}")


@app.post("/upload/{camera_id}", response_class=PlainTextResponse)
async def upload_image_for_camera(
    request: Request,
    camera_id: str,
    x_filename: Optional[str] = Header(default=None),
    _: str = Depends(get_current_username),
) -> PlainTextResponse:
    target_camera_id = _normalize_camera_id(camera_id)
    filename = _sanitize_filename(x_filename or "default.jpg")
    stored_filename, _ = await _store_uploaded_image(
        camera_id=target_camera_id,
        filename=filename,
        request=request,
        content_type=request.headers.get("content-type"),
    )
    logging.info("File saved for camera %s as %s", target_camera_id, stored_filename)
    return PlainTextResponse(f"File uploaded as {stored_filename}")


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response) -> AuthResponse:
    ensure_auth_configured()

    username = payload.username.strip()

    is_valid = secrets.compare_digest(username, AUTH_USERNAME) and secrets.compare_digest(payload.password, AUTH_PASSWORD)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    token, expires_in = create_session(username)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )

    return AuthResponse(expires_in=expires_in, username=username)


@app.get("/auth/me", response_model=MeResponse)
def me(username: str = Depends(get_current_username)) -> MeResponse:
    return MeResponse(username=username)


@app.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    token = resolve_session_token(request, credentials)
    if token:
        AUTH_SESSIONS.pop(token, None)
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}


@app.get("/config", response_model=AppConfig)
def get_config(_: str = Depends(get_current_username)) -> AppConfig:
    return CONFIG


@app.put("/config", response_model=AppConfig)
def update_config(payload: AppConfig, _: str = Depends(get_current_username)) -> AppConfig:
    global CONFIG
    CONFIG = payload
    return CONFIG


@app.get("/cameras/{camera_id}/config", response_model=AppConfig)
def get_camera_config(
    camera_id: str,
    _: str = Depends(get_current_username),
) -> AppConfig:
    return _read_camera_config(_normalize_camera_id(camera_id))


@app.put("/cameras/{camera_id}/config", response_model=AppConfig)
def update_camera_config(
    camera_id: str,
    payload: AppConfig,
    _: str = Depends(get_current_username),
) -> AppConfig:
    normalized = _normalize_camera_id(camera_id)
    _write_camera_config(normalized, payload)
    return payload


@app.get("/webcams")
def list_webcams(request: Request) -> list[dict]:
    webcams = get_webcams(str(request.base_url))
    for webcam in webcams:
        camera_id = _normalize_camera_id(str(webcam.get("id") or ""))
        latest_image_url = _latest_camera_image_url(camera_id)
        if not latest_image_url:
            continue
        webcam["thumbnail"] = latest_image_url
        webcam["currentImage"] = latest_image_url
    return webcams


@app.get("/history")
def get_history(
    hours: int = Query(24, ge=1, le=168),
    webcam_id: str | None = Query(default=None),
) -> list[dict]:
    camera_id = _normalize_camera_id(webcam_id)
    return generate_historical_data(hours, webcam_id=camera_id)


@app.get("/timeline")
def get_timeline(
    count: int = Query(48, ge=1, le=240),
    webcam_id: str | None = Query(default=None),
) -> list[dict]:
    camera_id = _normalize_camera_id(webcam_id)
    timeline = _timeline_from_camera_db(camera_id, count)
    if timeline is not None:
        return timeline
    return _timeline_from_image_dir(camera_id, count)


@app.get("/timezones")
def get_timezones() -> list[dict]:
    return TIMEZONES


@app.get("/weather/current")
async def get_current_weather(
    lat: float = Query(...),
    lon: float = Query(...),
    units: str = Query("metric"),
) -> dict:
    return await fetch_openweather("weather", lat, lon, units)


@app.get("/weather/forecast")
async def get_weather_forecast(
    lat: float = Query(...),
    lon: float = Query(...),
    units: str = Query("metric"),
) -> dict:
    return await fetch_openweather("forecast", lat, lon, units)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=parse_positive_int_env("PORT", 3000),
    )
