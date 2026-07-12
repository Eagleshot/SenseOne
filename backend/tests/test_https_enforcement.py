"""Tests for HTTPS enforcement middleware and the clock endpoint (SQLite-backed).

These build the full app via create_app(), which uses the database, so they run
against the test SQLite database. The pure auth_cookie_secure() unit test lives in
test_auth.py so it runs without a database.
"""

from fastapi.testclient import TestClient

from main import create_app
from station_hmac import provision_device_hmac_secret


def _client(tmp_data_dir, monkeypatch, *, require_https: bool, base_url: str = "http://testserver") -> TestClient:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    monkeypatch.setenv("APP_REQUIRE_HTTPS", "true" if require_https else "false")
    return TestClient(create_app(), base_url=base_url)


def test_clock_endpoint_returns_unix_seconds(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=False)
    response = client.get("/clock")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["unixSeconds"], int)
    assert payload["unixSeconds"] > 1_700_000_000


def test_https_enforcement_disabled_allows_plain_http_login(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=False)
    response = client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "nobody-secret"})
    assert response.status_code != 426


def test_https_enforcement_blocks_user_routes_over_http(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=True)
    response = client.post("/v1/auth/login", json={"email": "anyone@example.com", "password": "anyone-secret"})
    assert response.status_code == 426
    assert "HTTPS" in response.json()["detail"]


def test_https_enforcement_allows_device_routes_over_http(setup_station_dir, monkeypatch):
    """Signed device requests must still work over HTTP even with enforcement on."""
    data_dir, station_id = setup_station_dir
    provision_device_hmac_secret(station_id)
    client = _client(data_dir, monkeypatch, require_https=True)

    # Even without a valid signature, the device route is reachable: 401, not 426.
    response = client.post(f"/v1/ingest/stations/{station_id}/images", content=b"x")
    assert response.status_code == 401


def test_https_enforcement_allows_clock_over_http(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=True)
    assert client.get("/clock").status_code == 200


def test_https_enforcement_allows_health_over_http(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=True)
    assert client.get("/health").status_code == 200


def test_https_enforcement_passes_when_scheme_is_https(db, tmp_data_dir, monkeypatch):
    """Simulate a proxied request that arrived via HTTPS."""
    client = _client(tmp_data_dir, monkeypatch, require_https=True, base_url="https://testserver")
    response = client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "nobody-secret"})
    assert response.status_code != 426


def test_hsts_header_present_over_https(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=True, base_url="https://testserver")
    response = client.get("/clock")
    assert response.status_code == 200
    assert "strict-transport-security" in response.headers


def test_hsts_header_absent_over_http(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch, require_https=False)
    response = client.get("/clock")
    assert response.status_code == 200
    assert "strict-transport-security" not in response.headers


def test_login_sets_secure_httponly_cookie_under_https(db, tmp_data_dir, monkeypatch):
    """A successful HTTPS login issues a Secure, HttpOnly, SameSite=Strict session cookie."""
    monkeypatch.setenv("APP_AUTH_EMAIL", "admin@example.com")
    monkeypatch.setenv("APP_AUTH_PASSWORD", "correct-horse-battery")
    client = _client(tmp_data_dir, monkeypatch, require_https=True, base_url="https://testserver")

    response = client.post("/v1/auth/login", json={"email": "admin@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("set-cookie", "")
    assert "eagleshot_session=" in set_cookie
    assert "Secure" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=strict" in set_cookie.lower()
