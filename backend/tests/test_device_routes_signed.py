"""End-to-end tests for the HMAC-signed device routes.

Builds a minimal FastAPI app with just the two device routers, then drives
them through TestClient using the reference client signer. The point is to
catch any drift between the verifier, the dependency ordering, and the
Pydantic body parsing that could weaken authentication.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest
import sqlite3
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import station_db_path
from constants import STATION_CONFIG_FILENAME
from constants import DEVICE_API_PREFIX
from routes import device_ingestion
from station_hmac import generate_device_hmac_secret_b64, provision_device_hmac_secret


_CLIENT_SIGNER_PATH = (
    Path(__file__).resolve().parents[2] / "clients" / "python" / "eagleshot_signing.py"
)
_spec = importlib.util.spec_from_file_location("eagleshot_signing", _CLIENT_SIGNER_PATH)
assert _spec and _spec.loader
eagleshot_signing = importlib.util.module_from_spec(_spec)
sys.modules["eagleshot_signing"] = eagleshot_signing
_spec.loader.exec_module(eagleshot_signing)


# Real JPEG header bytes so the server's content-sniff accepts the upload.
_JPEG_BODY = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00" + b"\x08" * 64 + b"\xff\xd9"
)

_SENSOR_PAYLOAD = {
    "temperature": 12.5,
    "humidity": 78,
    "pressure": 1015,
    "battery": 91,
    "windSpeed": 3.2,
    "windDirection": 270,
    "visibility": 9.0,
    "uvIndex": 3,
    "dewPoint": 8.1,
    "feelsLike": 11.2,
}
_NEXT_ONLINE = "2026-05-23T12:30:00Z"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(device_ingestion.router, prefix=DEVICE_API_PREFIX)
    return app


@pytest.fixture
def signed_client(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    secret_b64 = provision_device_hmac_secret(station_id)
    client = TestClient(_build_app())
    return client, station_id, secret_b64


def _post_signed(
    client: TestClient,
    secret_b64: str,
    station_id: str,
    path: str,
    body: bytes,
    extra_headers: dict[str, str] | None = None,
):
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )
    if extra_headers:
        headers.update(extra_headers)
    return client.post(path, content=body, headers=headers)


def _get_signed(
    client: TestClient,
    secret_b64: str,
    station_id: str,
    path: str,
):
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="GET",
        path=path,
        body=b"",
    )
    return client.get(path, headers=headers)


def test_signed_device_config_succeeds(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/config"
    response = _get_signed(client, secret_b64, station_id, path)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stationStartTime"] == "06:00"
    assert body["stationStopTime"] == "20:00"
    assert body["captureIntervalMinutes"] == 30


def test_signed_device_config_rejects_missing_signature(signed_client):
    client, station_id, _ = signed_client
    response = client.get(f"{DEVICE_API_PREFIX}/stations/{station_id}/config")
    assert response.status_code == 401


def test_signed_device_config_rejects_wrong_secret(signed_client):
    client, station_id, _ = signed_client
    bogus_secret = generate_device_hmac_secret_b64()
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/config"
    response = _get_signed(client, bogus_secret, station_id, path)
    assert response.status_code == 401


def test_signed_image_upload_succeeds(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg", "X-Filename": "20260524_1430Z_front.jpg"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "20260524_1430Z_front.jpg"
    assert body["url"].endswith(body["filename"])


def test_signed_image_upload_rejects_malformed_filename(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg", "X-Filename": "capture.jpg"},
    )

    assert response.status_code == 422


def test_signed_image_upload_persists_next_online(signed_client):
    client, station_id, secret_b64 = signed_client
    data_dir = os.environ["APP_DATA_DIR"]
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={
            "Content-Type": "image/jpeg",
            "X-Filename": "20260524_1430Z_front.jpg",
            "X-Next-Online": _NEXT_ONLINE,
        },
    )
    assert response.status_code == 201, response.text

    with sqlite3.connect(station_db_path(Path(data_dir), station_id)) as connection:
        row = connection.execute(
            "SELECT next_online FROM station_images ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row == (_NEXT_ONLINE,)


def test_image_upload_without_signature_is_rejected(signed_client):
    client, station_id, _ = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/images"
    response = client.post(path, content=_JPEG_BODY, headers={"Content-Type": "image/jpeg"})
    assert response.status_code == 401


def test_image_upload_with_wrong_secret_is_rejected(signed_client):
    client, station_id, _ = signed_client
    bogus_secret = generate_device_hmac_secret_b64()
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, bogus_secret, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 401


def test_signed_sensor_reading_succeeds(signed_client):
    """Verifies dep-ordering: the HMAC dep consumes the body, then Pydantic still parses it."""
    client, station_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/sensor-readings"
    import json
    body = json.dumps(_SENSOR_PAYLOAD).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert parsed["temperature"] == _SENSOR_PAYLOAD["temperature"]
    assert parsed["humidity"] == _SENSOR_PAYLOAD["humidity"]


def test_signed_sensor_reading_persists_next_online(signed_client):
    import json

    client, station_id, secret_b64 = signed_client
    data_dir = os.environ["APP_DATA_DIR"]
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/sensor-readings"
    body = json.dumps({**_SENSOR_PAYLOAD, "nextStart": _NEXT_ONLINE}).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201, response.text

    with sqlite3.connect(station_db_path(Path(data_dir), station_id)) as connection:
        row = connection.execute(
            "SELECT timestamp, next_online FROM sensor_history ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row is not None
    assert row[1] == _NEXT_ONLINE

    config_doc = yaml.safe_load((Path(data_dir) / station_id / STATION_CONFIG_FILENAME).read_text())
    assert config_doc["last_online"] == row[0]
    assert config_doc["next_online"] == _NEXT_ONLINE


def test_signed_sparse_sensor_log_succeeds(signed_client):
    import json

    client, station_id, secret_b64 = signed_client
    data_dir = os.environ["APP_DATA_DIR"]
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/sensor-readings"
    body = json.dumps(
        {
            "timestamp": "2026-05-24T14:30:00Z",
            "firmwareVersion": "openmv-test",
            "nextStart": "2026-05-24T15:00:00Z",
            "cameraName": "front",
            "wakeReason": "timer",
            "voltage": 3.92,
        }
    ).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 201, response.text
    parsed = response.json()
    assert parsed["timestamp"] == "2026-05-24T14:30:00Z"
    assert parsed["temperature"] is None
    assert parsed["firmwareVersion"] == "openmv-test"
    assert parsed["nextStart"] == "2026-05-24T15:00:00Z"
    assert parsed["cameraName"] == "front"
    assert parsed["wakeReason"] == "timer"
    assert parsed["voltage"] == 3.92

    with sqlite3.connect(station_db_path(Path(data_dir), station_id)) as connection:
        row = connection.execute(
            """
            SELECT timestamp, voltage, firmware_version, next_start, camera_name, wake_reason, next_online
            FROM sensor_history
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert row == (
        "2026-05-24T14:30:00Z",
        3.92,
        "openmv-test",
        "2026-05-24T15:00:00Z",
        "front",
        "timer",
        "2026-05-24T15:00:00Z",
    )


def test_sensor_reading_without_signature_is_rejected(signed_client):
    client, station_id, _ = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/sensor-readings"
    import json
    response = client.post(
        path,
        content=json.dumps(_SENSOR_PAYLOAD).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_sensor_reading_with_tampered_body_is_rejected(signed_client):
    """Sign one payload, send a different one â€” signature should fail."""
    client, station_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{station_id}/sensor-readings"
    import json
    signed_body = json.dumps(_SENSOR_PAYLOAD).encode("utf-8")
    tampered = json.dumps({**_SENSOR_PAYLOAD, "battery": 1}).encode("utf-8")
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=signed_body,
    )
    headers["Content-Type"] = "application/json"
    response = client.post(path, content=tampered, headers=headers)
    assert response.status_code == 401


