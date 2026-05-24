"""Tests for API routing and public wire schemas."""

import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from main import create_app
from auth import AUTH_SESSIONS, create_session
from config import ensure_station_dir, write_station_config
from models import AppConfig
from station_hmac import provision_device_hmac_secret
from users import create_user


_CLIENT_SIGNER_PATH = (
    Path(__file__).resolve().parents[2] / "clients" / "python" / "eagleshot_signing.py"
)
_spec = importlib.util.spec_from_file_location("eagleshot_signing", _CLIENT_SIGNER_PATH)
assert _spec and _spec.loader
eagleshot_signing = importlib.util.module_from_spec(_spec)
sys.modules["eagleshot_signing"] = eagleshot_signing
_spec.loader.exec_module(eagleshot_signing)


TEST_USERNAME = "api-test-admin"
TEST_PASSWORD = "correct-horse-battery-staple"


def _client(tmp_data_dir, monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    AUTH_SESSIONS.clear()
    app = create_app()
    try:
        create_user(TEST_USERNAME, TEST_PASSWORD, is_admin=True)
    except ValueError:
        pass
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    token, _ = create_session(TEST_USERNAME)
    return {"Authorization": f"Bearer {token}"}


def _station(tmp_data_dir, station_id: str = "station-1") -> str:
    ensure_station_dir(tmp_data_dir, station_id)
    write_station_config(
        tmp_data_dir,
        station_id,
        AppConfig(
            title="Station One",
            location="Test Ridge",
            country="Switzerland",
            country_emoji="CH",
            is_public=True,
        ),
    )
    return station_id


def test_auth_uses_camel_case_response(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)

    response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["expiresIn"] > 0
    assert payload["isAdmin"] is True
    assert "expires_in" not in payload
    assert "is_admin" not in payload


def test_station_responses_use_camel_case(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    client = _client(tmp_data_dir, monkeypatch)

    list_response = client.get("/stations")
    detail_response = client.get(f"/stations/{station_id}")

    assert list_response.status_code == 200
    summary = list_response.json()[0]
    assert summary["isPublic"] is True
    assert "is_public" not in summary

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["isPublic"] is True
    assert "is_public" not in detail


def test_station_config_accepts_and_returns_camel_case(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    client = _client(tmp_data_dir, monkeypatch)
    headers = _auth_headers()

    get_response = client.get(f"/stations/{station_id}/config", headers=headers)
    assert get_response.status_code == 200
    config = get_response.json()
    assert config["stationStartTime"] == "06:00"
    assert config["captureIntervalMinutes"] == 30
    assert config["isPublic"] is True
    assert "station_start_time" not in config
    assert "is_public" not in config

    config["stationStartTime"] = "07:00"
    config["stationStopTime"] = "19:00"
    config["isPublic"] = False
    put_response = client.put(f"/stations/{station_id}/config", json=config, headers=headers)

    assert put_response.status_code == 200
    updated = put_response.json()
    assert updated["stationStartTime"] == "07:00"
    assert updated["stationStopTime"] == "19:00"
    assert updated["isPublic"] is False


def test_rotate_key_route_is_gone(tmp_data_dir, monkeypatch):
    """The legacy API-key rotation endpoint has been removed in favour of HMAC."""
    station_id = _station(tmp_data_dir)
    client = _client(tmp_data_dir, monkeypatch)

    response = client.post(f"/stations/{station_id}/rotate-key", headers=_auth_headers())
    assert response.status_code == 404


_JPEG_BODY = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00" + b"\x08" * 64 + b"\xff\xd9"
)


def test_device_image_route_accepts_signed_request(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    secret_b64 = provision_device_hmac_secret(station_id)
    client = _client(tmp_data_dir, monkeypatch)

    path = f"/device/stations/{station_id}/images"
    signed_headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=_JPEG_BODY,
    )
    response = client.post(
        path,
        headers={**signed_headers, "X-Filename": "capture.jpg", "Content-Type": "image/jpeg"},
        content=_JPEG_BODY,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["filename"].endswith("-capture.jpg")
    assert payload["url"] == f"/stations/{station_id}/images/{payload['filename']}"


def test_sensor_device_route_is_registered(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    client = _client(tmp_data_dir, monkeypatch)

    response = client.post(f"/device/stations/{station_id}/sensor-readings", json={})

    assert response.status_code in (401, 422)


def test_sensor_reading_accepts_signed_request(tmp_data_dir, monkeypatch):
    import json as _json
    station_id = _station(tmp_data_dir)
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    secret_b64 = provision_device_hmac_secret(station_id)
    client = _client(tmp_data_dir, monkeypatch)

    path = f"/device/stations/{station_id}/sensor-readings"
    body = _json.dumps({
        "timestamp": "2026-05-23T12:00:00Z",
        "temperature": 21.5,
        "humidity": 58,
        "pressure": 1012,
        "battery": 87,
        "windSpeed": 4.2,
        "windDirection": 225,
        "visibility": 9.5,
        "uvIndex": 3,
        "dewPoint": 13.1,
        "feelsLike": 20.9,
    }).encode("utf-8")
    signed_headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )

    response = client.post(
        path,
        headers={**signed_headers, "Content-Type": "application/json"},
        content=body,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["windSpeed"] == 4.2
    assert payload["uvIndex"] == 3
    assert "wind_speed" not in payload


def test_sensor_reading_rejects_session_cookie_without_hmac_signature(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    client = _client(tmp_data_dir, monkeypatch)
    login_response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )

    response = client.post(
        f"/device/stations/{station_id}/sensor-readings",
        json={
            "temperature": 21.5,
            "humidity": 58,
            "pressure": 1012,
            "battery": 87,
            "windSpeed": 4.2,
            "windDirection": 225,
            "visibility": 9.5,
            "uvIndex": 3,
            "dewPoint": 13.1,
            "feelsLike": 20.9,
        },
    )

    assert login_response.status_code == 200
    assert response.status_code == 401


def test_renamed_station_data_routes_are_registered(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    client = _client(tmp_data_dir, monkeypatch)

    assert client.get(f"/stations/{station_id}/image-captures").status_code == 200
    assert client.get(f"/stations/{station_id}/sensor-readings").status_code == 200
    assert client.get(f"/stations/{station_id}/sensor-series").status_code == 404

    assert client.get(f"/stations/{station_id}/timeline").status_code == 404
    assert client.get(f"/stations/{station_id}/history").status_code == 404
    assert client.get(f"/stations/{station_id}/chart-data-sources").status_code == 404


def test_image_captures_do_not_fall_back_to_filesystem(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    images_dir = tmp_data_dir / station_id / "images"
    images_dir.joinpath("20240101_1200Z-orphan.jpg").write_bytes(_JPEG_BODY)
    client = _client(tmp_data_dir, monkeypatch)

    response = client.get(f"/stations/{station_id}/image-captures")

    assert response.status_code == 200
    assert response.json() == []


def test_removed_legacy_routes_are_not_registered(tmp_data_dir, monkeypatch):
    station_id = _station(tmp_data_dir)
    client = _client(tmp_data_dir, monkeypatch)

    for method, path in (
        ("post", "/upload"),
        ("post", f"/upload/{station_id}"),
        ("post", f"/sensors/{station_id}/readings"),
        ("post", "/v1/auth/login"),
        ("get", "/v1/stations"),
        ("post", "/v1/upload"),
        ("post", f"/v1/upload/{station_id}"),
        ("post", f"/v1/sensors/{station_id}/readings"),
        ("post", f"/v1/device/stations/{station_id}/sensor-readings"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 404


def test_health_stays_unversioned(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)

    assert client.get("/health").status_code == 200
    assert client.get("/v1/health").status_code == 404


def test_openapi_lists_frontend_and_device_paths(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)

    paths = client.get("/openapi.json").json()["paths"]

    assert "/health" in paths
    assert "/auth/login" in paths
    assert "/stations" in paths
    assert "/stations/{station_id}/image-captures" in paths
    assert "/stations/{station_id}/sensor-readings" in paths
    assert "/stations/{station_id}/sensor-series" not in paths
    assert "/clock" in paths
    assert "/server-time" not in paths
    assert "/v1/clock" not in paths
    assert "/device/stations/{station_id}/images" in paths
    assert "/device/stations/{station_id}/sensor-readings" in paths
    assert "/v1/auth/login" not in paths
    assert "/v1/stations" not in paths
    assert "/stations/{station_id}/timeline" not in paths
    assert "/stations/{station_id}/history" not in paths
    assert "/stations/{station_id}/chart-data-sources" not in paths
    assert "/stations/{station_id}/rotate-key" not in paths
    assert "/upload" not in paths
    assert "/upload/{station_id}" not in paths
    assert "/sensors/{station_id}/readings" not in paths
    assert "/upload/{station_id}" not in paths
    assert "/sensors/{station_id}/readings" not in paths


