"""Endpoint tests for station metadata, image timeline, and sensor history."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from constants import API_V1_PREFIX
from auth import get_optional_current_user
from config import write_station_config
from models import AppConfig
from routes import stations


def _client(data_dir, monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    app = FastAPI()
    app.include_router(stations.router, prefix=API_V1_PREFIX)
    app.dependency_overrides[get_optional_current_user] = lambda: None
    return TestClient(app)


def test_list_stations_empty(tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)

    response = client.get("/v1/stations")

    assert response.status_code == 200
    assert response.json() == []


def test_list_stations_returns_visible_station(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    client = _client(data_dir, monkeypatch)

    response = client.get("/v1/stations")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [station_id]
    assert body[0]["name"] == "Test Station"
    assert body[0]["coordinates"] == {"lat": 47.5, "lng": 8.5, "altitude": 1000.0}


def test_private_station_is_hidden_from_anonymous_list(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    write_station_config(data_dir, station_id, AppConfig(is_public=False))
    client = _client(data_dir, monkeypatch)

    response = client.get("/v1/stations")

    assert response.status_code == 200
    assert response.json() == []


def test_station_detail_includes_latest_image(station_with_sample_images, monkeypatch):
    data_dir, station_id = station_with_sample_images
    client = _client(data_dir, monkeypatch)

    response = client.get(f"/v1/stations/{station_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == station_id
    assert body["currentImage"] == f"/stations/{station_id}/images/0-test.jpg"
    assert body["lastUpdate"] is not None
    assert body["nextUpdate"] is not None


def test_station_detail_includes_latest_battery(station_with_history, monkeypatch):
    data_dir, station_id = station_with_history
    client = _client(data_dir, monkeypatch)

    response = client.get(f"/v1/stations/{station_id}")

    assert response.status_code == 200
    assert response.json()["battery"] == 95


def test_image_captures_are_oldest_to_newest_and_respect_count(station_with_sample_images, monkeypatch):
    data_dir, station_id = station_with_sample_images
    client = _client(data_dir, monkeypatch)

    response = client.get(f"/v1/stations/{station_id}/image-captures?count=2")

    assert response.status_code == 200
    assert [item["url"] for item in response.json()] == [
        f"/stations/{station_id}/images/1-test.jpg",
        f"/stations/{station_id}/images/0-test.jpg",
    ]


def test_sensor_readings_use_requested_window(station_with_history, monkeypatch):
    data_dir, station_id = station_with_history
    client = _client(data_dir, monkeypatch)

    response = client.get(f"/v1/stations/{station_id}/sensor-readings?hours=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body) <= 2
    assert {"timestamp", "temperature", "humidity", "battery", "windSpeed", "uvIndex"} <= set(body[0])
