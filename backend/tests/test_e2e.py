"""End-to-end tests for the control-plane backend, driving the real HTTP routes.

Runs against a throwaway SQLite database (TEST_DATABASE_URL, defaulting to a temp
file) — no server needed. The fixture builds the schema directly (Base.metadata)
and seeds a minimal set through the same app layer the routes use, then drives the
real HTTP routes.
"""

import json

import pytest
from fastapi.testclient import TestClient

from tests._db import TEST_DATABASE_URL as TEST_DB, stamp_head
from tests._signing import sign_request

_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\xff\xdb\x00C\x00" + b"\x08" * 64 + b"\xff\xd9"


@pytest.fixture
def seeded_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DB)
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    import db.session as session_module

    session_module._engine = None  # force a fresh engine bound to TEST_DATABASE_URL
    session_module._sessionmaker = None

    from db.models import Base
    from db.session import get_engine

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    stamp_head()  # so create_app()'s startup `alembic upgrade head` is a no-op

    import store
    import users
    from main import create_app
    from models import StationCreateRequest

    alice = users.create_user("alice@example.com", "devpassword123")
    public_slug = store.create_station(StationCreateRequest(title="Public Cam", is_public=True), alice)
    private_slug = store.create_station(StationCreateRequest(title="Private Cam", is_public=False), alice)

    return TestClient(create_app()), public_slug, private_slug


def test_anonymous_visibility(seeded_client):
    client, public_slug, private_slug = seeded_client
    listed = [s["id"] for s in client.get("/v1/stations").json()]
    assert public_slug in listed
    assert private_slug not in listed
    assert client.get(f"/v1/stations/{private_slug}").status_code == 404


def test_owner_login_and_private_access(seeded_client):
    client, _, private_slug = seeded_client
    assert client.post("/v1/auth/login", json={"email": "alice@example.com", "password": "devpassword123"}).status_code == 200
    assert private_slug in [s["id"] for s in client.get("/v1/stations").json()]
    assert client.get(f"/v1/stations/{private_slug}").status_code == 200


def test_config_round_trip(seeded_client):
    client, _, private_slug = seeded_client
    client.post("/v1/auth/login", json={"email": "alice@example.com", "password": "devpassword123"})
    cfg = client.get(f"/v1/stations/{private_slug}/config").json()
    cfg["captureIntervalMinutes"] = 15
    assert client.put(f"/v1/stations/{private_slug}/config", json=cfg).status_code == 200
    assert client.get(f"/v1/stations/{private_slug}/config").json()["captureIntervalMinutes"] == 15


def test_signed_device_flow(seeded_client):
    client, public_slug, _ = seeded_client
    client.post("/v1/auth/login", json={"email": "alice@example.com", "password": "devpassword123"})
    secret = client.post(f"/v1/stations/{public_slug}/rotate-device-secret").json()["deviceHmacSecret"]

    s_path = f"/v1/ingest/stations/{public_slug}/data"
    body = json.dumps({"readings": [{"temperature": 1.2, "battery": 88}]}).encode()
    headers = sign_request(station_id=public_slug, secret_b64=secret, method="POST", path=s_path, body=body)
    headers["Content-Type"] = "application/json"
    assert client.post(s_path, content=body, headers=headers).status_code == 204

    i_path = f"/v1/ingest/stations/{public_slug}/images"
    headers = sign_request(station_id=public_slug, secret_b64=secret, method="POST", path=i_path, body=_JPEG)
    headers.update({"Content-Type": "image/jpeg", "X-Filename": "20260601_1200Z_front.jpg"})
    assert client.post(i_path, content=_JPEG, headers=headers).status_code == 201

    assert len(client.get(f"/v1/stations/{public_slug}/data?hours=24").json()) >= 1
    caps = client.get(f"/v1/stations/{public_slug}/image-captures?count=5").json()
    assert len(caps) == 1
    # image-captures returns API-origin-relative URLs (no /v1); prepend it to hit
    # the versioned mount directly (the proxy does this transparently in the browser).
    assert client.get(f"/v1{caps[0]['url']}").status_code == 200

    bad = sign_request(station_id=public_slug, secret_b64="AAAA", method="POST", path=s_path, body=body)
    bad["Content-Type"] = "application/json"
    assert client.post(s_path, content=body, headers=bad).status_code == 401
