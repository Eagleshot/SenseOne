"""End-to-end tests for the HMAC-signed device routes (SQLite-backed).

Builds a minimal FastAPI app with just the device routers, then drives them
through TestClient using the reference client signer — catching drift between the
verifier, dependency ordering, and Pydantic body parsing that could weaken auth.
"""

import json
import os
import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from constants import INGEST_API_PREFIX
from db import station_repo
from models import AppConfigUpdate
from routes import device_ingestion
from security import generate_device_hmac_secret_b64
from station_hmac import provision_device_hmac_secret
from tests import _db
from tests import _signing as eagleshot_signing

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
}
_NEXT_ONLINE = "2026-05-23T12:30:00Z"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(device_ingestion.router, prefix=INGEST_API_PREFIX)
    return app


@pytest.fixture
def signed_client(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    secret_b64 = provision_device_hmac_secret(station_id)
    client = TestClient(_build_app())
    return client, station_id, secret_b64


def _post_signed(client, secret_b64, station_id, path, body, extra_headers=None):
    extra_headers = dict(extra_headers or {})
    # X-Filename is part of the signature; the rest (e.g. Content-Type) is not.
    x_filename = extra_headers.pop("X-Filename", "")
    headers = eagleshot_signing.sign_request(
        station_id=station_id, secret_b64=secret_b64, method="POST", path=path, body=body,
        x_filename=x_filename,
    )
    headers.update(extra_headers)
    return client.post(path, content=body, headers=headers)


def _get_signed(client, secret_b64, station_id, path):
    headers = eagleshot_signing.sign_request(
        station_id=station_id, secret_b64=secret_b64, method="GET", path=path, body=b"",
    )
    return client.get(path, headers=headers)


def test_signed_device_config_succeeds(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/config"
    response = _get_signed(client, secret_b64, station_id, path)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stationStartMinute"] == 360
    assert body["stationStopMinute"] == 1200
    assert body["captureIntervalMinutes"] == 30
    # The frozen, filename-safe station name token the device uses for capture filenames.
    assert body["name"] == "test-station"
    # Fields the device may need for sunrise/sunset are present...
    for key in ("useSunriseSunset", "lat", "lon", "alt"):
        assert key in body
    # ...while UI-only fields are trimmed out of the device payload.
    for key in ("stationStartTime", "countryEmoji", "title", "isPublic"):
        assert key not in body


def test_signed_device_config_unknown_altitude_falls_back_to_zero(signed_client):
    """Firmware expects a plain number, so a null (unknown) altitude is sent as 0.0."""
    client, station_id, secret_b64 = signed_client
    station_repo.save_station_config(station_id, AppConfigUpdate(alt=None))

    path = f"{INGEST_API_PREFIX}/stations/{station_id}/config"
    response = _get_signed(client, secret_b64, station_id, path)

    assert response.status_code == 200, response.text
    assert response.json()["alt"] == 0.0


def test_signed_device_config_rejects_missing_signature(signed_client):
    client, station_id, _ = signed_client
    response = client.get(f"{INGEST_API_PREFIX}/stations/{station_id}/config")
    assert response.status_code == 401


def test_signed_device_config_rejects_wrong_secret(signed_client):
    client, station_id, _ = signed_client
    bogus_secret = generate_device_hmac_secret_b64()
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/config"
    response = _get_signed(client, bogus_secret, station_id, path)
    assert response.status_code == 401


def test_signed_image_upload_succeeds(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
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
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg", "X-Filename": "capture.jpg"},
    )
    assert response.status_code == 422


def test_signed_image_upload_defaults_filename_when_omitted(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg"},  # X-Filename omitted on purpose
    )
    assert response.status_code == 201, response.text
    filename = response.json()["filename"]
    # The server stamps the current minute and injects the station's frozen name token.
    assert re.fullmatch(r"\d{8}_\d{4}Z_test-station\.jpg", filename), filename
    assert _db.latest_image(station_id)["filename"] == filename


def test_signed_image_upload_expands_bare_timestamp_filename(signed_client):
    # A device may upload just the timestamp; the server injects the station name.
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg", "X-Filename": "20260524_1430Z.jpg"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["filename"] == "20260524_1430Z_test-station.jpg"


def test_signed_image_upload_rejects_tampered_filename(signed_client):
    """Sign one X-Filename, send a different (still valid-format) one — must fail.

    X-Filename sets the stored image's capture timestamp/stream, so it is part of
    the signature; an on-path attacker relabelling it can no longer slip through.
    """
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    headers = eagleshot_signing.sign_request(
        station_id=station_id, secret_b64=secret_b64, method="POST", path=path, body=_JPEG_BODY,
        x_filename="20260524_1430Z_front.jpg",
    )
    headers["X-Filename"] = "20251201_0000Z_front.jpg"  # forge the capture time
    headers["Content-Type"] = "image/jpeg"
    response = client.post(path, content=_JPEG_BODY, headers=headers)
    assert response.status_code == 401


def test_image_upload_without_signature_is_rejected(signed_client):
    client, station_id, _ = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    response = client.post(path, content=_JPEG_BODY, headers={"Content-Type": "image/jpeg"})
    assert response.status_code == 401


def test_unknown_station_is_401_not_404(signed_client):
    """Signed routes must not reveal which station ids exist to unauthenticated callers."""
    client, _, secret_b64 = signed_client
    bogus_station = "aaaabbbbcccc"
    path = f"{INGEST_API_PREFIX}/stations/{bogus_station}/images"
    response = _post_signed(
        client, secret_b64, bogus_station, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 401


def test_image_upload_with_wrong_secret_is_rejected(signed_client):
    client, station_id, _ = signed_client
    bogus_secret = generate_device_hmac_secret_b64()
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, bogus_secret, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 401


def test_image_upload_rejected_when_disk_nearly_full(signed_client, monkeypatch):
    import image_store

    client, station_id, secret_b64 = signed_client
    monkeypatch.setenv("APP_MIN_FREE_DISK_BYTES", str(500 * 1024 * 1024))
    monkeypatch.setattr(
        image_store.shutil, "disk_usage",
        lambda _path: SimpleNamespace(total=1, used=1, free=1024),
    )
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg", "X-Filename": "20260524_1430Z_front.jpg"},
    )
    assert response.status_code == 507, response.text
    assert not (
        os.environ["APP_DATA_DIR"] and
        _db.latest_image(station_id) is not None
    )


def test_image_upload_allowed_when_disk_guard_disabled(signed_client, monkeypatch):
    import image_store

    client, station_id, secret_b64 = signed_client
    monkeypatch.setenv("APP_MIN_FREE_DISK_BYTES", "0")
    monkeypatch.setattr(
        image_store.shutil, "disk_usage",
        lambda _path: SimpleNamespace(total=1, used=1, free=0),
    )
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/images"
    response = _post_signed(
        client, secret_b64, station_id, path, _JPEG_BODY,
        extra_headers={"Content-Type": "image/jpeg", "X-Filename": "20260524_1430Z_front.jpg"},
    )
    assert response.status_code == 201, response.text


def test_signed_sensor_reading_succeeds(signed_client):
    """Verifies dep-ordering: the HMAC dep consumes the body, then Pydantic still parses it."""
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    body = json.dumps({"readings": [_SENSOR_PAYLOAD]}).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )
    # Success is a bare 204 with no body.
    assert response.status_code == 204, response.text
    assert response.content == b""
    stored = _db.latest_reading(station_id)["metrics"]
    assert stored["temperature"] == _SENSOR_PAYLOAD["temperature"]
    assert stored["humidity"] == _SENSOR_PAYLOAD["humidity"]
    # windSpeed is an unregistered metric: accepted and stored, just without a unit.
    assert stored["windSpeed"] == _SENSOR_PAYLOAD["windSpeed"]


def test_signed_sensor_reading_persists_next_online(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    body = json.dumps({"readings": [_SENSOR_PAYLOAD], "nextStart": _NEXT_ONLINE}).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 204, response.text
    assert _db.latest_reading(station_id)["next_online"] == _NEXT_ONLINE


def test_signed_multi_channel_reading_persists_each_channel(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    body = json.dumps(
        {
            "wakeReason": "timer",
            "readings": [
                {"channel": "indoor", "temperature": 21.4, "humidity": 55},
                {"channel": "outdoor", "temperature": 5.1},
            ],
        }
    ).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 204, response.text
    # One envelope, observations split across the two channels' datastreams.
    observations = _db.sensor_observations(station_id)
    assert {"metric": "temperature", "channel": "indoor", "value": 21.4} in observations
    assert {"metric": "temperature", "channel": "outdoor", "value": 5.1} in observations
    assert {"metric": "humidity", "channel": "indoor", "value": 55.0} in observations


def test_signed_sparse_sensor_log_succeeds(signed_client):
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    body = json.dumps(
        {
            "timestamp": "2026-05-24T14:30:00Z",
            "firmwareVersion": "openmv-test",
            "nextStart": "2026-05-24T15:00:00Z",
            "wakeReason": "timer",
            "readings": [{"voltage": 3.92}],
        }
    ).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    row = _db.latest_reading(station_id)
    assert row["recorded_at"] == "2026-05-24T14:30:00Z"
    assert row["next_online"] == "2026-05-24T15:00:00Z"
    # firmware/wake are envelope labels, not measurements.
    assert row["firmware_version"] == "openmv-test"
    assert row["wake_reason"] == "timer"
    assert row["metrics"] == {"voltage": 3.92}


def test_envelope_only_heartbeat_succeeds(signed_client):
    """A check-in with no readings is a valid online-status heartbeat (no observations)."""
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    body = json.dumps(
        {"timestamp": "2026-05-24T14:30:00Z", "nextStart": _NEXT_ONLINE}
    ).encode("utf-8")
    response = _post_signed(
        client, secret_b64, station_id, path, body,
        extra_headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 204, response.text
    row = _db.latest_reading(station_id)
    assert row["next_online"] == _NEXT_ONLINE
    assert row["metrics"] == {}


@pytest.mark.parametrize(
    "payload",
    [
        # Duplicate channel: both readings collapse to the "default" channel.
        pytest.param({"readings": [{"temperature": 1.0}, {"temperature": 2.0}]}, id="duplicate-channel"),
        # The old flat shape (metrics at the top level) is no longer accepted.
        pytest.param({"temperature": 21.0}, id="flat-top-level-metric"),
        # Envelope labels (wakeReason/firmwareVersion) belong at the top level, not in a reading.
        pytest.param({"readings": [{"temperature": 1.0, "wakeReason": "timer"}]}, id="reserved-label-in-reading"),
        # 9 channels x 64 metrics = 576 observations, over the 512 per-check-in cap (each
        # reading is within the 64-field per-reading limit, so only the total cap can trip).
        pytest.param(
            {"readings": [{"channel": f"c{i}", **{f"m{j}": 1.0 for j in range(64)}} for i in range(9)]},
            id="too-many-observations",
        ),
    ],
)
def test_invalid_sensor_payload_is_rejected(signed_client, payload):
    """Malformed sensor payloads are rejected with 422 before anything is stored."""
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    response = _post_signed(
        client, secret_b64, station_id, path, json.dumps(payload).encode("utf-8"),
        extra_headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text


def test_sensor_reading_without_signature_is_rejected(signed_client):
    client, station_id, _ = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    response = client.post(
        path,
        content=json.dumps({"readings": [_SENSOR_PAYLOAD]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_sensor_reading_with_tampered_body_is_rejected(signed_client):
    """Sign one payload, send a different one — signature should fail."""
    client, station_id, secret_b64 = signed_client
    path = f"{INGEST_API_PREFIX}/stations/{station_id}/data"
    signed_body = json.dumps({"readings": [_SENSOR_PAYLOAD]}).encode("utf-8")
    tampered = json.dumps({"readings": [{**_SENSOR_PAYLOAD, "battery": 1}]}).encode("utf-8")
    headers = eagleshot_signing.sign_request(
        station_id=station_id, secret_b64=secret_b64, method="POST", path=path, body=signed_body,
    )
    headers["Content-Type"] = "application/json"
    response = client.post(path, content=tampered, headers=headers)
    assert response.status_code == 401
