"""End-to-end tests for the HMAC-signed device routes.

Builds a minimal FastAPI app with just the two device routers, then drives
them through TestClient using the reference client signer. The point is to
catch any drift between the verifier, the dependency ordering, and the
Pydantic body parsing that could weaken authentication.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(device_ingestion.router, prefix=DEVICE_API_PREFIX)
    return app


@pytest.fixture
def signed_client(setup_camera_dir, monkeypatch):
    data_dir, camera_id = setup_camera_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    secret_b64 = provision_device_hmac_secret(camera_id)
    client = TestClient(_build_app())
    return client, camera_id, secret_b64


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


def test_signed_image_upload_succeeds(signed_client):
    client, camera_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{camera_id}/images"
    response = _post_signed(
        client, secret_b64, camera_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg", "X-Filename": "capture.jpg"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"].endswith("-capture.jpg")
    assert body["url"].endswith(body["filename"])


def test_image_upload_without_signature_is_rejected(signed_client):
    client, camera_id, _ = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{camera_id}/images"
    response = client.post(path, content=_JPEG_BODY, headers={"Content-Type": "image/jpeg"})
    assert response.status_code == 401


def test_image_upload_with_wrong_secret_is_rejected(signed_client):
    client, camera_id, _ = signed_client
    bogus_secret = generate_device_hmac_secret_b64()
    path = f"{DEVICE_API_PREFIX}/stations/{camera_id}/images"
    response = _post_signed(
        client, bogus_secret, camera_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 401


def test_signed_sensor_reading_succeeds(signed_client):
    """Verifies dep-ordering: the HMAC dep consumes the body, then Pydantic still parses it."""
    client, camera_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{camera_id}/sensor-readings"
    import json
    body = json.dumps(_SENSOR_PAYLOAD).encode("utf-8")
    response = _post_signed(
        client, secret_b64, camera_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert parsed["temperature"] == _SENSOR_PAYLOAD["temperature"]
    assert parsed["humidity"] == _SENSOR_PAYLOAD["humidity"]


def test_sensor_reading_without_signature_is_rejected(signed_client):
    client, camera_id, _ = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{camera_id}/sensor-readings"
    import json
    response = client.post(
        path,
        content=json.dumps(_SENSOR_PAYLOAD).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_sensor_reading_with_tampered_body_is_rejected(signed_client):
    """Sign one payload, send a different one — signature should fail."""
    client, camera_id, secret_b64 = signed_client
    path = f"{DEVICE_API_PREFIX}/stations/{camera_id}/sensor-readings"
    import json
    signed_body = json.dumps(_SENSOR_PAYLOAD).encode("utf-8")
    tampered = json.dumps({**_SENSOR_PAYLOAD, "battery": 1}).encode("utf-8")
    headers = eagleshot_signing.sign_request(
        station_id=camera_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=signed_body,
    )
    headers["Content-Type"] = "application/json"
    response = client.post(path, content=tampered, headers=headers)
    assert response.status_code == 401
