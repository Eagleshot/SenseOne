"""Tests for HTTPS enforcement middleware and the clock endpoint."""

from fastapi.testclient import TestClient

from main import create_app
from auth import AUTH_SESSIONS
from station_hmac import provision_device_hmac_secret


def _client(tmp_data_dir, monkeypatch, *, require_https: bool) -> TestClient:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    monkeypatch.setenv("APP_REQUIRE_HTTPS", "true" if require_https else "false")
    AUTH_SESSIONS.clear()
    return TestClient(create_app())


def test_clock_endpoint_returns_unix_seconds(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=False)
    response = client.get("/clock")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["unixSeconds"], int)
    assert payload["unixSeconds"] > 1_700_000_000  # sanity check: after 2023


def test_https_enforcement_disabled_allows_plain_http_login(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=False)
    # No user configured, so login returns 401, but the request reaches the
    # auth route rather than being short-circuited by the HTTPS middleware.
    response = client.post(
        "/auth/login",
        json={"username": "nobody", "password": "nobody"},
    )
    assert response.status_code != 426


def test_https_enforcement_blocks_user_routes_over_http(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=True)
    response = client.post(
        "/auth/login",
        json={"username": "anyone", "password": "anyone"},
    )
    assert response.status_code == 426
    assert "HTTPS" in response.json()["detail"]


def test_https_enforcement_allows_device_routes_over_http(tmp_data_dir, monkeypatch, setup_station_dir):
    """Signed device requests must still work over HTTP even with enforcement on."""
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    provision_device_hmac_secret(station_id)

    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    monkeypatch.setenv("APP_REQUIRE_HTTPS", "true")
    AUTH_SESSIONS.clear()
    client = TestClient(create_app())

    # Even without a valid signature, the device route should at least be
    # reachable: it rejects with 401, not 426.
    response = client.post(f"/device/stations/{station_id}/images", content=b"x")
    assert response.status_code == 401


def test_https_enforcement_allows_clock_over_http(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=True)
    response = client.get("/clock")
    assert response.status_code == 200


def test_https_enforcement_allows_health_over_http(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=True)
    response = client.get("/health")
    assert response.status_code == 200


def test_https_enforcement_passes_when_scheme_is_https(tmp_data_dir, monkeypatch):
    """Simulate a proxied request that arrived via HTTPS."""
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    monkeypatch.setenv("APP_REQUIRE_HTTPS", "true")
    AUTH_SESSIONS.clear()
    # Setting base_url with https:// flips request.url.scheme to "https" inside
    # the app, the same way --proxy-headers would behind a real reverse proxy.
    client = TestClient(create_app(), base_url="https://testserver")
    response = client.post(
        "/auth/login",
        json={"username": "nobody", "password": "nobody"},
    )
    # 401/503/etc: anything but 426 means the middleware let it through.
    assert response.status_code != 426
