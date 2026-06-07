"""Eagleshot Python API client"""

from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request

SIGNATURE_VERSION = "v1"
NONCE_BYTES = 16


def _b64decode_urlsafe_nopad(value: str) -> bytes:
    """Decode a base64url secret that may be stored without ``=`` padding."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def canonical_signing_string(
    *,
    station_id: str,
    timestamp: int,
    nonce: str,
    method: str,
    path: str,
    body_sha256_hex: str,
) -> bytes:
    """Build the canonical string fed to HMAC. Mirrors the server exactly."""
    return "\n".join((
        SIGNATURE_VERSION,
        station_id,
        str(int(timestamp)),
        nonce,
        method.upper(),
        path,
        body_sha256_hex,
    )).encode("ascii")


def sign_request(
    *,
    station_id: str,
    secret_b64: str,
    method: str,
    path: str,
    body: bytes,
    timestamp: int | None = None,
    nonce_hex: str | None = None,
) -> dict[str, str]:
    """Return the four signed-request headers for a device call.

    ``timestamp`` defaults to the current unix time and ``nonce_hex`` to a fresh
    16-byte random hex string; pass them explicitly only for tests.
    """
    if timestamp is None:
        timestamp = int(time.time())
    if nonce_hex is None:
        nonce_hex = os.urandom(NONCE_BYTES).hex()

    canonical = canonical_signing_string(
        station_id=station_id,
        timestamp=timestamp,
        nonce=nonce_hex,
        method=method,
        path=path,
        body_sha256_hex=hashlib.sha256(body).hexdigest(),
    )
    secret = _b64decode_urlsafe_nopad(secret_b64)
    signature_hex = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    return {
        "X-Station-Id": station_id,
        "X-Timestamp": str(int(timestamp)),
        "X-Nonce": nonce_hex,
        "X-Signature": f"{SIGNATURE_VERSION}={signature_hex}",
    }


class EagleshotClient:
    """Signs and sends the signed device calls for one station over HTTP.

    Most methods return ``(status_code, response_text)`` on a 2xx response, raise
    :class:`urllib.error.HTTPError` on a non-2xx response (its ``.read()`` still
    carries the server's JSON detail), and :class:`urllib.error.URLError` when the
    host is unreachable. The exception is :meth:`health`, which returns a ``bool``
    and never raises.
    """

    def __init__(self, *, base_url: str = "http://api.eagleshot.org", station_id: str, secret_b64: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.station_id = station_id
        self.secret_b64 = secret_b64
        self.timeout = timeout

    def _send(self, *, method: str, path: str, body: bytes, extra_headers: dict[str, str] | None = None) -> tuple[int, str]:
        headers = sign_request(
            station_id=self.station_id,
            secret_b64=self.secret_b64,
            method=method,
            path=path,
            body=body,
        )
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(
            self.base_url + path,
            data=None if method == "GET" else body,
            method=method,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.status, response.read().decode("utf-8")

    def send_sensor_reading(
        self,
        readings: dict[str, float] | list[dict],
        *,
        timestamp: datetime | None = None,
        next_start: datetime | None = None,
        firmware_version: str | None = None,
        wake_reason: str | None = None,
    ) -> tuple[int, str]:
        """POST one device check-in: a shared envelope plus per-channel readings.

        ``readings`` is either a single metrics dict (lands on the ``default``
        channel) or a list of per-channel dicts, each a channel's metrics with an
        optional ``channel`` key; resolved channels must be unique. Metric keys
        beyond the known set are stored verbatim. Returns ``(status, text)``; a
        successful POST is HTTP 204 with an empty body.
        """
        if isinstance(readings, dict):
            readings = [readings]
        body: dict = {"readings": [dict(reading) for reading in readings]}
        if timestamp:
            body["timestamp"] = timestamp.replace(microsecond=0).isoformat()
        if next_start:
            body["nextStart"] = next_start.replace(microsecond=0).isoformat()
        if firmware_version:
            body["firmwareVersion"] = firmware_version
        if wake_reason:
            body["wakeReason"] = wake_reason
        return self._send(
            method="POST",
            path=f"/v1/ingest/stations/{self.station_id}/data",
            body=json.dumps(body).encode("utf-8"),
            extra_headers={"Content-Type": "application/json"},
        )

    def upload_image(
        self,
        image_bytes: bytes,
        *,
        content_type: str,
        filename: str | None = None,
    ) -> tuple[int, str]:
        """POST one image as raw bytes. ``filename`` (X-Filename) must be YYYYMMDD_HHMMZ_<camera>.<ext>."""
        extra = {"Content-Type": content_type}
        if filename:
            extra["X-Filename"] = filename
        return self._send(
            method="POST",
            path=f"/v1/ingest/stations/{self.station_id}/images",
            body=image_bytes,
            extra_headers=extra,
        )

    def get_config(self) -> tuple[int, str]:
        """GET the device's capture schedule + location config (signed, no body)."""
        return self._send(
            method="GET",
            path=f"/v1/ingest/stations/{self.station_id}/config",
            body=b"",
        )

    def health(self) -> bool:
        """Returns ``True`` if the Eagleshot API is reachable and responding."""
        request = urllib.request.Request(self.base_url + "/health", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status == 200
        except urllib.error.URLError:
            return False
