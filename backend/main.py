from __future__ import annotations

import logging
import os
import re
import secrets
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

try:
    from .mock_data import TIMEZONES, generate_historical_data, generate_image_timestamps, get_webcams
except ImportError:
    from mock_data import TIMEZONES, generate_historical_data, generate_image_timestamps, get_webcams


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


def parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


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
AUTH_MAX_LOGIN_ATTEMPTS = parse_positive_int_env("APP_AUTH_MAX_LOGIN_ATTEMPTS", 5)
AUTH_LOCKOUT_SECONDS = parse_positive_int_env("APP_AUTH_LOCKOUT_SECONDS", 300)
AUTH_RATE_LIMIT_WINDOW_SECONDS = parse_positive_int_env("APP_AUTH_RATE_LIMIT_WINDOW_SECONDS", 900)

APP_CORS_ORIGINS = parse_cors_origins()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
TRUST_PROXY_HEADERS = parse_bool_env("APP_TRUST_PROXY_HEADERS", False)
TRUSTED_PROXY_IPS = {
    ip.strip() for ip in (os.getenv("APP_TRUSTED_PROXY_IPS") or "").split(",") if ip.strip()
}
RATE_LIMIT_MAX_REQUESTS = parse_positive_int_env("APP_RATE_LIMIT_MAX_REQUESTS", 60)
RATE_LIMIT_WINDOW_SECONDS = parse_positive_int_env("APP_RATE_LIMIT_WINDOW_SECONDS", 60)

BASE_DIR = Path(__file__).resolve().parent
EXAMPLE_IMAGES_DIR = BASE_DIR / "example_images"
UPLOAD_DIR = BASE_DIR / "uploads"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
if not AUTH_ENABLED:
    logging.warning("Authentication is disabled because APP_AUTH_USERNAME/APP_AUTH_PASSWORD are not set.")

app = FastAPI(title="Eagleshot API", version="0.1.0")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/example_images", StaticFiles(directory=EXAMPLE_IMAGES_DIR), name="example_images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Filename"],
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
FAILED_LOGIN_ATTEMPTS: dict[str, tuple[int, float, float]] = {}
RATE_LIMIT_STATE: dict[str, tuple[int, float]] = {}
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


def get_client_ip(request: Request) -> str:
    direct_client_ip = request.client.host if request.client and request.client.host else ""
    if TRUST_PROXY_HEADERS and direct_client_ip and direct_client_ip in TRUSTED_PROXY_IPS:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            forwarded_client_ip = forwarded_for.split(",")[0].strip()
            if forwarded_client_ip:
                return forwarded_client_ip
    if direct_client_ip:
        return direct_client_ip
    return "unknown"


def get_login_attempt_key(request: Request) -> str:
    return get_client_ip(request)


def enforce_login_rate_limit(key: str) -> None:
    state = FAILED_LOGIN_ATTEMPTS.get(key)
    if state is None:
        return

    attempts, window_started_at, blocked_until = state
    now = time.time()

    if blocked_until > now:
        retry_after = max(1, int(blocked_until - now))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Try again in {retry_after} seconds.",
        )

    if now - window_started_at > AUTH_RATE_LIMIT_WINDOW_SECONDS:
        FAILED_LOGIN_ATTEMPTS.pop(key, None)
        return

    FAILED_LOGIN_ATTEMPTS[key] = (attempts, window_started_at, blocked_until)


def register_failed_login(key: str) -> None:
    now = time.time()
    attempts, window_started_at, blocked_until = FAILED_LOGIN_ATTEMPTS.get(key, (0, now, 0))

    if now - window_started_at > AUTH_RATE_LIMIT_WINDOW_SECONDS:
        attempts = 0
        window_started_at = now
        blocked_until = 0

    attempts += 1
    if attempts >= AUTH_MAX_LOGIN_ATTEMPTS:
        FAILED_LOGIN_ATTEMPTS[key] = (0, now, now + AUTH_LOCKOUT_SECONDS)
        return

    FAILED_LOGIN_ATTEMPTS[key] = (attempts, window_started_at, blocked_until)


def register_successful_login(key: str) -> None:
    FAILED_LOGIN_ATTEMPTS.pop(key, None)


def enforce_rate_limit(request: Request, bucket: str = "global") -> None:
    now = time.time()
    stale_keys = [
        key
        for key, (_, window_started_at) in RATE_LIMIT_STATE.items()
        if now - window_started_at > RATE_LIMIT_WINDOW_SECONDS
    ]
    for key in stale_keys:
        RATE_LIMIT_STATE.pop(key, None)

    client_ip = get_client_ip(request)
    rate_key = f"{bucket}:{client_ip}"
    request_count, window_started_at = RATE_LIMIT_STATE.get(rate_key, (0, now))

    if now - window_started_at > RATE_LIMIT_WINDOW_SECONDS:
        request_count = 0
        window_started_at = now

    request_count += 1
    RATE_LIMIT_STATE[rate_key] = (request_count, window_started_at)

    if request_count <= RATE_LIMIT_MAX_REQUESTS:
        return

    retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - window_started_at)))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many requests. Try again in {retry_after} seconds.",
    )


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in ("/", "/health", "/favicon.ico"):
        return await call_next(request)
    enforce_rate_limit(request, bucket="global")
    return await call_next(request)


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
    x_filename: Optional[str] = Header(default=None),
) -> PlainTextResponse:
    filename = _sanitize_filename(x_filename or "default.jpg")
    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as target:
        async for chunk in request.stream():
            target.write(chunk)

    logging.info("File saved as %s", filename)
    return PlainTextResponse(f"File uploaded as {filename}")


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    ensure_auth_configured()

    username = payload.username.strip()
    attempt_key = get_login_attempt_key(request)
    enforce_login_rate_limit(attempt_key)

    is_valid = secrets.compare_digest(username, AUTH_USERNAME) and secrets.compare_digest(payload.password, AUTH_PASSWORD)
    if not is_valid:
        register_failed_login(attempt_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    register_successful_login(attempt_key)
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


@app.get("/webcams")
def list_webcams(request: Request) -> list[dict]:
    return get_webcams(str(request.base_url))


@app.get("/history")
def get_history(
    hours: int = Query(24, ge=1, le=168),
    webcam_id: str | None = Query(default=None),
) -> list[dict]:
    _ = webcam_id
    return generate_historical_data(hours)


@app.get("/timeline")
def get_timeline(
    request: Request,
    count: int = Query(48, ge=1, le=240),
    webcam_id: str | None = Query(default=None),
) -> list[dict]:
    _ = webcam_id
    return generate_image_timestamps(str(request.base_url), count)


@app.get("/timezones")
def get_timezones() -> list[dict]:
    return TIMEZONES


@app.get("/weather/current")
async def get_current_weather(
    request: Request,
    lat: float = Query(...),
    lon: float = Query(...),
    units: str = Query("metric"),
) -> dict:
    enforce_rate_limit(request, bucket="weather")
    return await fetch_openweather("weather", lat, lon, units)


@app.get("/weather/forecast")
async def get_weather_forecast(
    request: Request,
    lat: float = Query(...),
    lon: float = Query(...),
    units: str = Query("metric"),
) -> dict:
    enforce_rate_limit(request, bucket="weather")
    return await fetch_openweather("forecast", lat, lon, units)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=parse_positive_int_env("PORT", 3000),
    )
