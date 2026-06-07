"""Tests for API routing and public wire schemas (SQLite-backed).

The public HTTP surface is versioned under ``/v1``: the browser/app API at
``/v1/...`` and device ingestion at ``/v1/ingest/...``. Only the unversioned
infrastructure endpoints (``/``, ``/health``, ``/clock``, ``/favicon.ico``) live
at the root. These tests pin that contract so an accidental mount change — or a
regression to the old unversioned paths — is caught.
"""

import json

import pytest
from fastapi.testclient import TestClient

from auth import AUTH_SESSIONS, create_session
from main import create_app
from station_hmac import provision_device_hmac_secret
from users import create_user
from tests import _db
from tests import _signing as eagleshot_signing

TEST_EMAIL = "api-test-admin@example.com"
TEST_PASSWORD = "correct-horse-battery-staple"

_JPEG_BODY = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00" + b"\x08" * 64 + b"\xff\xd9"
)


@pytest.fixture
def client(db, tmp_data_dir, monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    AUTH_SESSIONS.clear()
    app = create_app()
    try:
        create_user(TEST_EMAIL, TEST_PASSWORD, is_admin=True)
    except ValueError:
        pass
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    token, _ = create_session(TEST_EMAIL)
    return {"Authorization": f"Bearer {token}"}


def _station(station_id: str = "station-1") -> str:
    return _db.create_station_row(
        station_id, is_public=True, title="Station One",
        location="Test Ridge", country="Switzerland", country_emoji="CH",
    )


def test_auth_uses_camel_case_response(client):
    response = client.post("/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert response.status_code == 200
    payload = response.json()
    assert payload["expiresIn"] > 0
    assert payload["isAdmin"] is True
    assert "expires_in" not in payload
    assert "is_admin" not in payload


def test_station_responses_use_camel_case(client):
    station_id = _station()
    summary = client.get("/v1/stations").json()[0]
    assert summary["isPublic"] is True
    assert "is_public" not in summary

    detail = client.get(f"/v1/stations/{station_id}").json()
    assert detail["isPublic"] is True
    assert "is_public" not in detail


def test_station_config_accepts_and_returns_camel_case(client):
    station_id = _station()
    headers = _auth_headers()

    config = client.get(f"/v1/stations/{station_id}/config", headers=headers).json()
    assert config["stationStartTime"] == "06:00"
    assert config["captureIntervalMinutes"] == 30
    assert config["isPublic"] is True
    assert "station_start_time" not in config
    assert "is_public" not in config

    config["stationStartTime"] = "07:00"
    config["stationStopTime"] = "19:00"
    config["isPublic"] = False
    put_response = client.put(f"/v1/stations/{station_id}/config", json=config, headers=headers)

    assert put_response.status_code == 200
    updated = put_response.json()
    assert updated["stationStartTime"] == "07:00"
    assert updated["stationStopTime"] == "19:00"
    assert updated["isPublic"] is False


def test_rotate_key_route_is_gone(client):
    station_id = _station()
    response = client.post(f"/v1/stations/{station_id}/rotate-key", headers=_auth_headers())
    assert response.status_code == 404


def test_device_image_route_accepts_signed_request(client):
    station_id = _station()
    secret_b64 = provision_device_hmac_secret(station_id)

    path = f"/v1/ingest/stations/{station_id}/images"
    signed_headers = eagleshot_signing.sign_request(
        station_id=station_id, secret_b64=secret_b64, method="POST", path=path, body=_JPEG_BODY,
        x_filename="20260524_1430Z_front.jpg",
    )
    response = client.post(
        path,
        headers={**signed_headers, "Content-Type": "image/jpeg"},
        content=_JPEG_BODY,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["filename"] == "20260524_1430Z_front.jpg"
    # Image URLs are returned relative to the API origin (no version prefix).
    assert payload["url"] == f"/stations/{station_id}/images/{payload['filename']}"


def test_sensor_device_route_is_registered(client):
    station_id = _station()
    response = client.post(f"/v1/ingest/stations/{station_id}/data", json={})
    assert response.status_code in (401, 422)


def test_sensor_reading_accepts_signed_request(client):
    station_id = _station()
    secret_b64 = provision_device_hmac_secret(station_id)

    path = f"/v1/ingest/stations/{station_id}/data"
    body = json.dumps({
        "timestamp": "2026-05-23T12:00:00Z",
        "readings": [{
            "temperature": 21.5,
            "humidity": 58,
            "windSpeed": 4.2,
            "uvIndex": 3,
        }],
    }).encode("utf-8")
    signed_headers = eagleshot_signing.sign_request(
        station_id=station_id, secret_b64=secret_b64, method="POST", path=path, body=body,
    )
    response = client.post(path, headers={**signed_headers, "Content-Type": "application/json"}, content=body)

    assert response.status_code == 204, response.text
    # camelCase measurement keys are preserved verbatim (unregistered metrics are
    # still accepted); no snake_case rewriting happens.
    stored = {obs["metric"]: obs["value"] for obs in _db.sensor_observations(station_id)}
    assert stored["windSpeed"] == 4.2
    assert stored["uvIndex"] == 3
    assert "wind_speed" not in stored


def test_sensor_reading_rejects_session_cookie_without_hmac_signature(client):
    station_id = _station()
    login_response = client.post("/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    response = client.post(
        f"/v1/ingest/stations/{station_id}/data",
        json={"readings": [{"temperature": 21.5, "humidity": 58, "battery": 87}]},
    )
    assert login_response.status_code == 200
    assert response.status_code == 401


def test_renamed_station_data_routes_are_registered(client):
    station_id = _station()
    assert client.get(f"/v1/stations/{station_id}/image-captures").status_code == 200
    assert client.get(f"/v1/stations/{station_id}/data").status_code == 200
    assert client.get(f"/v1/stations/{station_id}/sensor-series").status_code == 404
    assert client.get(f"/v1/stations/{station_id}/timeline").status_code == 404
    assert client.get(f"/v1/stations/{station_id}/history").status_code == 404


def test_image_captures_do_not_fall_back_to_filesystem(client, tmp_data_dir):
    station_id = _station()
    images_dir = tmp_data_dir / station_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    images_dir.joinpath("20240101_1200Z-orphan.jpg").write_bytes(_JPEG_BODY)

    response = client.get(f"/v1/stations/{station_id}/image-captures")
    assert response.status_code == 200
    assert response.json() == []


def test_unversioned_and_legacy_routes_are_not_registered(client):
    station_id = _station()
    # Everything except the infra endpoints now lives under /v1/ingest (device)
    # or /v1 (app); the old unversioned paths, the renamed-away /v1/device
    # prefix, and the long-removed legacy routes must all 404.
    for method, path in (
        ("post", "/auth/login"),
        ("get", "/stations"),
        ("get", f"/stations/{station_id}"),
        ("post", f"/device/stations/{station_id}/sensor-readings"),
        ("post", f"/v1/device/stations/{station_id}/sensor-readings"),
        ("post", "/upload"),
        ("post", f"/upload/{station_id}"),
        ("post", f"/sensors/{station_id}/readings"),
    ):
        assert getattr(client, method)(path).status_code == 404, f"{method} {path}"


def test_health_and_clock_stay_unversioned(client):
    assert client.get("/health").status_code == 200
    assert client.get("/clock").status_code == 200
    assert client.get("/v1/health").status_code == 404
    assert client.get("/v1/clock").status_code == 404


def test_openapi_lists_versioned_and_infra_paths(client):
    paths = client.get("/openapi.json").json()["paths"]
    # Infra endpoints stay unversioned.
    assert "/health" in paths
    assert "/clock" in paths
    # App + device API are versioned under /v1.
    assert "/v1/auth/login" in paths
    assert "/v1/stations" in paths
    assert "/v1/stations/{station_id}/image-captures" in paths
    assert "/v1/stations/{station_id}/data" in paths
    assert "/v1/ingest/stations/{station_id}/images" in paths
    assert "/v1/ingest/stations/{station_id}/config" in paths
    assert "/v1/ingest/stations/{station_id}/data" in paths
    # The unversioned app paths and removed route names are gone.
    assert "/auth/login" not in paths
    assert "/stations" not in paths
    assert "/v1/stations/{station_id}/rotate-key" not in paths
    assert "/upload" not in paths
