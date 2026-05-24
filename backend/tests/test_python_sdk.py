"""Tests for the Python SDK client wrappers."""

import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path

import httpx


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "clients" / "python"))

from eagleshot import APIError, EagleshotClient, EagleshotDeviceClient  # noqa: E402
from eagleshot.signing import canonical_signing_string  # noqa: E402


SECRET_B64 = base64.urlsafe_b64encode(b"x" * 32).rstrip(b"=").decode("ascii")


def _secret_bytes() -> bytes:
    return base64.urlsafe_b64decode(SECRET_B64 + "=" * (-len(SECRET_B64) % 4))


def _assert_valid_signature(request: httpx.Request, station_id: str, signing_path: str) -> None:
    timestamp = int(request.headers["X-Timestamp"])
    nonce = request.headers["X-Nonce"]
    expected = hmac.new(
        _secret_bytes(),
        canonical_signing_string(
            station_id=station_id,
            timestamp=timestamp,
            nonce_hex=nonce,
            method=request.method,
            path=signing_path,
            body=request.content,
        ),
        hashlib.sha256,
    ).hexdigest()
    assert request.headers["X-Station-Id"] == station_id
    assert request.headers["X-Signature"] == f"v1={expected}"


def test_user_client_keeps_login_cookie_and_preserves_base_path():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={"expiresIn": 3600, "username": "admin", "isAdmin": True},
                headers={"set-cookie": "eagleshot_session=abc; Path=/; HttpOnly"},
            )
        if request.url.path == "/api/auth/me":
            assert request.headers["cookie"] == "eagleshot_session=abc"
            return httpx.Response(200, json={"username": "admin", "isAdmin": True})
        raise AssertionError(f"Unexpected request path: {request.url.path}")

    api = EagleshotClient("http://backend.example/api", transport=httpx.MockTransport(handler))
    assert api.login("admin", "password")["username"] == "admin"
    assert api.me()["isAdmin"] is True
    api.close()

    assert [request.url.path for request in requests] == ["/api/auth/login", "/api/auth/me"]


def test_update_station_config_accepts_pythonic_keys():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stations/test-station/config"
        assert json.loads(request.content) == {
            "stationStartTime": "07:00",
            "captureIntervalMinutes": 15,
        }
        return httpx.Response(200, json={"stationStartTime": "07:00", "captureIntervalMinutes": 15})

    api = EagleshotClient("http://backend.example", transport=httpx.MockTransport(handler))
    response = api.update_station_config(
        "test-station",
        {"station_start_time": "07:00", "capture_interval_minutes": 15},
    )
    api.close()

    assert response["captureIntervalMinutes"] == 15


def test_api_error_normalizes_fastapi_validation_details():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": [{"msg": "Value must be greater than 0"}]})

    api = EagleshotClient("http://backend.example", transport=httpx.MockTransport(handler))
    try:
        api.get_station_sensor_readings("test-station", hours=0)
    except APIError as exc:
        assert exc.status_code == 422
        assert exc.detail == "Value must be greater than 0"
    else:
        raise AssertionError("Expected APIError")
    finally:
        api.close()


def test_device_config_signs_backend_path_when_base_url_has_proxy_prefix():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/device/stations/test-station/config"
        assert request.content == b""
        _assert_valid_signature(request, "test-station", "/device/stations/test-station/config")
        return httpx.Response(200, json={"stationStartTime": "06:00"})

    device = EagleshotDeviceClient(
        "http://frontend.example/api",
        "test-station",
        SECRET_B64,
        transport=httpx.MockTransport(handler),
    )

    assert device.get_config()["stationStartTime"] == "06:00"
    device.close()


def test_device_sensor_upload_camelizes_payload_and_signs_exact_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/device/stations/test-station/sensor-readings"
        assert request.headers["content-type"] == "application/json"
        assert request.content == b'{"temperature":12.5,"nextStart":"2026-05-24T15:00:00Z"}'
        _assert_valid_signature(request, "test-station", "/device/stations/test-station/sensor-readings")
        return httpx.Response(201, json={"temperature": 12.5, "nextStart": "2026-05-24T15:00:00Z"})

    device = EagleshotDeviceClient(
        "http://backend.example",
        "test-station",
        SECRET_B64,
        transport=httpx.MockTransport(handler),
    )

    response = device.upload_sensor_reading(
        {"temperature": 12.5, "next_start": "2026-05-24T15:00:00Z"}
    )
    device.close()

    assert response["temperature"] == 12.5


def test_device_image_upload_sends_required_headers():
    image = b"\xff\xd8\xff\xe0fake-jpeg"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/device/stations/test-station/images"
        assert request.headers["x-filename"] == "20260524_1430Z_front.jpg"
        assert request.headers["x-next-online"] == "2026-05-24T15:00:00Z"
        assert request.headers["content-type"] == "image/jpeg"
        assert request.content == image
        _assert_valid_signature(request, "test-station", "/device/stations/test-station/images")
        return httpx.Response(201, json={"filename": "20260524_1430Z_front.jpg", "url": "/stations/test-station/images/20260524_1430Z_front.jpg"})

    device = EagleshotDeviceClient(
        "http://backend.example",
        "test-station",
        SECRET_B64,
        transport=httpx.MockTransport(handler),
    )

    response = device.upload_image(
        image,
        filename="20260524_1430Z_front.jpg",
        next_online="2026-05-24T15:00:00Z",
    )
    device.close()

    assert response["filename"] == "20260524_1430Z_front.jpg"
