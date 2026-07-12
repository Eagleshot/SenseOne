"""Tests for the user-route request-body cap (main.add_body_size_limit_middleware).

User-facing routes carry small JSON only; oversized bodies are rejected before
they buffer into memory. The signed ingest routes are exempt — they carry
images and enforce their own caps in routes/device_ingestion.py.
"""

from fastapi.testclient import TestClient

from main import MAX_USER_BODY_BYTES, create_app


def _client(tmp_data_dir, monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    return TestClient(create_app())


def test_oversized_user_body_is_rejected_with_413(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)
    body = b"x" * (MAX_USER_BODY_BYTES + 1)
    response = client.post(
        "/v1/auth/login", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_normal_user_body_passes_the_cap(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)
    response = client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "nobody-secret-123"}
    )
    # 401/503 (bad credentials / no users) proves it reached the route, not 413.
    assert response.status_code in (401, 503)


def test_ingest_routes_are_exempt_from_the_user_cap(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    client = _client(data_dir, monkeypatch)
    body = b"x" * (MAX_USER_BODY_BYTES + 1)
    response = client.post(f"/v1/ingest/stations/{station_id}/images", content=body)
    # The ingest route applies its own (image-sized) caps after auth: an
    # unsigned request 401s — it must NOT be 413'd by the user-route cap.
    assert response.status_code == 401
