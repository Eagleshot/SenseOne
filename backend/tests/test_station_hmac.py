"""Round-trip tests for the device HMAC signing scheme.

Exercises the server-side verifier against the reference client signer so any
drift between the two implementations fails the build.
"""

import asyncio
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from security import generate_device_hmac_secret_b64
from station_hmac import (
    SIGNATURE_VERSION,
    TIMESTAMP_SKEW_SECONDS,
    provision_device_hmac_secret,
    verify_station_signature,
)

from tests import _signing as eagleshot_signing


def _build_request(method: str, path: str, headers: dict[str, str], body: bytes) -> Request:
    """Build a minimal Starlette Request that yields `body` from request.body()."""
    header_pairs = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": header_pairs,
    }
    sent = {"done": False}

    async def receive() -> dict:
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive=receive)


@pytest.fixture
def provisioned_station(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    secret_b64 = provision_device_hmac_secret(station_id)
    return station_id, secret_b64


def _sign_and_verify(station_id: str, secret_b64: str, body: bytes = b"hello") -> bytes:
    path = f"/v1/ingest/stations/{station_id}/images"
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )
    request = _build_request("POST", path, headers, body)
    return asyncio.run(verify_station_signature(station_id, request))


def test_valid_signature_is_accepted(provisioned_station):
    station_id, secret_b64 = provisioned_station
    returned_body = _sign_and_verify(station_id, secret_b64, body=b"a tiny image")
    assert returned_body == b"a tiny image"


def test_oversized_body_is_rejected_with_413(provisioned_station):
    """The body is read before the signature verdict, so it must be capped —
    the request here carries no Content-Length (like chunked encoding)."""
    station_id, secret_b64 = provisioned_station
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"x" * 64
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )
    request = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request, max_body_bytes=16))
    assert exc.value.status_code == 413


def test_unprovisioned_station_oversized_body_also_413s(setup_station_dir, monkeypatch):
    """The body cap applies before the secret lookup: if only provisioned
    stations 413'd an oversized body, the 401/413 difference would reveal which
    station ids are provisioned — the probe the shared generic 401 prevents."""
    data_dir, station_id = setup_station_dir  # station exists, but no secret
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"x" * 64
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=generate_device_hmac_secret_b64(),
        method="POST",
        path=path,
        body=body,
    )
    request = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request, max_body_bytes=16))
    assert exc.value.status_code == 413


def test_replayed_nonce_is_rejected(provisioned_station):
    station_id, secret_b64 = provisioned_station
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"payload"
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )

    first = _build_request("POST", path, headers, body)
    asyncio.run(verify_station_signature(station_id, first))

    second = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, second))
    assert exc.value.status_code == 401
    assert "nonce" in exc.value.detail.lower()


def test_stale_timestamp_is_rejected(provisioned_station):
    station_id, secret_b64 = provisioned_station
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"x"
    stale_ts = int(time.time()) - TIMESTAMP_SKEW_SECONDS - 60
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
        timestamp=stale_ts,
    )
    request = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request))
    assert exc.value.status_code == 401
    assert "timestamp" in exc.value.detail.lower()


def test_tampered_body_is_rejected(provisioned_station):
    station_id, secret_b64 = provisioned_station
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"original"
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )
    request = _build_request("POST", path, headers, b"tampered")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request))
    assert exc.value.status_code == 401
    assert "signature" in exc.value.detail.lower()


def test_wrong_secret_is_rejected(provisioned_station):
    station_id, _ = provisioned_station
    # An attacker who doesn't know the real secret picks a random one.
    bogus_b64 = generate_device_hmac_secret_b64()
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"x"
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=bogus_b64,
        method="POST",
        path=path,
        body=body,
    )
    request = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request))
    assert exc.value.status_code == 401


def test_station_without_secret_is_rejected(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    # Note: provision_device_hmac_secret is NOT called for this station.
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"x"
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=generate_device_hmac_secret_b64(),
        method="POST",
        path=path,
        body=body,
    )
    request = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request))
    assert exc.value.status_code == 401
    # The detail must NOT reveal that the station simply has no secret provisioned:
    # it is the same generic message a provisioned station gives for a bad
    # signature, so callers can't probe which ids exist/are provisioned.
    assert exc.value.detail == "Signature verification failed."


def test_station_id_mismatch_is_rejected(provisioned_station):
    station_id, secret_b64 = provisioned_station
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"x"
    headers = eagleshot_signing.sign_request(
        station_id="some-other-station",
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )
    request = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request))
    assert exc.value.status_code == 401


def test_signature_version_prefix_is_required(provisioned_station):
    station_id, secret_b64 = provisioned_station
    path = f"/v1/ingest/stations/{station_id}/images"
    body = b"x"
    headers = eagleshot_signing.sign_request(
        station_id=station_id,
        secret_b64=secret_b64,
        method="POST",
        path=path,
        body=body,
    )
    # Strip the "v1=" prefix to simulate an old/bad client.
    headers["X-Signature"] = headers["X-Signature"][len(SIGNATURE_VERSION) + 1:]
    request = _build_request("POST", path, headers, body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_station_signature(station_id, request))
    assert exc.value.status_code == 401


