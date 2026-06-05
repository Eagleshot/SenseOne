"""Endpoint tests for station metadata, image timeline, and sensor history (SQLite-backed)."""

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user, get_optional_current_user
from routes import stations
from tests import _db


@dataclass(frozen=True)
class RouteUser:
    owner_id: str
    is_admin: bool = False


def _client(monkeypatch, user=None) -> TestClient:
    app = FastAPI()
    app.include_router(stations.router)
    app.dependency_overrides[get_optional_current_user] = lambda: None
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_list_stations_empty(db, monkeypatch):
    response = _client(monkeypatch).get("/stations")
    assert response.status_code == 200
    assert response.json() == []


def test_list_stations_returns_visible_station(setup_station_dir, monkeypatch):
    _, station_id = setup_station_dir
    response = _client(monkeypatch).get("/stations")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [station_id]
    assert body[0]["name"] == "Test Station"
    assert body[0]["coordinates"] == {"lat": 47.5, "lng": 8.5, "altitude": 1000.0}


def test_private_station_is_hidden_from_anonymous_list(setup_station_dir, monkeypatch):
    _, station_id = setup_station_dir
    _db.set_station_public(station_id, False)
    response = _client(monkeypatch).get("/stations")
    assert response.status_code == 200
    assert response.json() == []


def test_list_stations_reports_can_edit_per_row(db, monkeypatch):
    owner = _db.create_owner("owner@example.com")
    other = _db.create_owner("other@example.com")
    _db.create_station_row("owned", is_public=True, owner_id=owner.owner_id)
    _db.create_station_row("foreign", is_public=True, owner_id=other.owner_id)

    def can_edit_map(user):
        app = FastAPI()
        app.include_router(stations.router)
        app.dependency_overrides[get_optional_current_user] = lambda: user
        body = TestClient(app).get("/stations").json()
        return {item["id"]: item["canEdit"] for item in body}

    assert can_edit_map(RouteUser(owner.owner_id)) == {"owned": True, "foreign": False}
    assert can_edit_map(RouteUser("00000000-0000-0000-0000-000000000000", is_admin=True)) == {
        "owned": True,
        "foreign": True,
    }
    assert can_edit_map(None) == {"owned": False, "foreign": False}


def test_create_station_assigns_owner_and_private_default(db, monkeypatch):
    owner = _db.create_owner("owner@example.com")
    client = _client(monkeypatch, RouteUser(owner.owner_id))

    response = client.post("/stations", json={"title": "Peak Camera"})

    assert response.status_code == 201
    body = response.json()
    # id is opaque + stable; the human-friendly slug lives in urlSlug.
    assert body["urlSlug"] == "Peak-Camera"
    assert body["id"] and body["id"] != "Peak-Camera"
    assert body["name"] == "Peak Camera"
    assert body["isPublic"] is False
    assert _db.station_owner_id(body["id"]) == owner.owner_id


def test_create_station_auto_suffixes_duplicate_urlslug(setup_station_dir, monkeypatch):
    # setup_station_dir created a station with url_slug "test-station".
    owner = _db.create_owner("owner@example.com")
    client = _client(monkeypatch, RouteUser(owner.owner_id))

    response = client.post("/stations", json={"title": "test station", "isPublic": True})

    assert response.status_code == 201
    body = response.json()
    assert body["urlSlug"] == "test-station-2"
    assert body["isPublic"] is True


def test_rename_changes_url_slug_not_id(setup_station_dir, monkeypatch):
    # setup_station_dir: public_id == url_slug == "test-station".
    _, station_id = setup_station_dir
    admin = RouteUser("00000000-0000-0000-0000-000000000000", is_admin=True)
    client = _client(monkeypatch, admin)

    cfg = client.get(f"/stations/{station_id}/config").json()
    cfg["title"] = "Renamed Cam"
    assert client.put(f"/stations/{station_id}/config", json=cfg).status_code == 200

    detail = client.get(f"/stations/{station_id}").json()
    assert detail["id"] == station_id          # opaque id is stable
    assert detail["urlSlug"] == "Renamed-Cam"  # pretty slug followed the rename
    assert detail["name"] == "Renamed Cam"


def test_station_detail_includes_latest_image(station_with_sample_images, monkeypatch):
    _, station_id = station_with_sample_images
    response = _client(monkeypatch).get(f"/stations/{station_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == station_id
    assert body["currentImage"] == f"/stations/{station_id}/images/0-test.jpg"
    assert body["lastUpdate"] is not None
    assert body["nextUpdate"] is None


def test_station_detail_can_edit_reflects_ownership(setup_station_dir, monkeypatch):
    _, station_id = setup_station_dir
    owner_id = _db.station_owner_id(station_id)

    # Anonymous viewer of a public station cannot edit it.
    assert _client(monkeypatch).get(f"/stations/{station_id}").json()["canEdit"] is False

    # The owner can.
    app = FastAPI()
    app.include_router(stations.router)
    app.dependency_overrides[get_optional_current_user] = lambda: RouteUser(owner_id)
    owner_client = TestClient(app)
    assert owner_client.get(f"/stations/{station_id}").json()["canEdit"] is True


def test_station_detail_includes_latest_battery(station_with_history, monkeypatch):
    _, station_id = station_with_history
    response = _client(monkeypatch).get(f"/stations/{station_id}")

    assert response.status_code == 200
    assert response.json()["battery"] == 95


def test_station_detail_uses_db_runtime_timestamps(setup_station_dir, monkeypatch):
    _, station_id = setup_station_dir
    _db.add_reading(
        station_id,
        "2026-05-23T12:00:00Z",
        {"temperature": 21.5, "humidity": 58, "pressure": 1012, "battery": 87, "reception": 73},
        next_online="2026-05-23T12:30:00Z",
    )
    response = _client(monkeypatch).get(f"/stations/{station_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["lastUpdate"] == "2026-05-23T12:00:00Z"
    assert body["nextUpdate"] == "2026-05-23T12:30:00Z"


def test_image_captures_are_oldest_to_newest_and_respect_count(station_with_sample_images, monkeypatch):
    _, station_id = station_with_sample_images
    response = _client(monkeypatch).get(f"/stations/{station_id}/image-captures?count=2")

    assert response.status_code == 200
    assert [item["url"] for item in response.json()] == [
        f"/stations/{station_id}/images/1-test.jpg",
        f"/stations/{station_id}/images/0-test.jpg",
    ]


def test_sensor_readings_use_requested_window(station_with_history, monkeypatch):
    _, station_id = station_with_history
    response = _client(monkeypatch).get(f"/stations/{station_id}/sensor-readings?hours=2")

    assert response.status_code == 200
    body = response.json()
    # One series per metric the fixture wrote.
    metrics = {series["metric"] for series in body}
    assert {"temperature", "humidity", "battery", "reception"} <= metrics
    for series in body:
        assert series["channel"] == "default"
        assert len(series["points"]) <= 3  # window covers at most readings i=0,1,2
        assert {"timestamp", "value"} <= set(series["points"][0])
    # battery is a registered metric, so its series is unit-tagged.
    battery = next(series for series in body if series["metric"] == "battery")
    assert battery["unit"] == "percent"
