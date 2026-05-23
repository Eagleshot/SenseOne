"""Verify the OpenMV (MicroPython) signer matches the CPython reference.

If these implementations ever diverge, device-signed requests will be rejected
by the server. Loading both modules into CPython and comparing outputs on
fixed inputs catches any drift.
"""

import importlib.util
import sys
from pathlib import Path

import pytest


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def signers():
    repo = Path(__file__).resolve().parents[2]
    cpy = _load("eagleshot_signing_cpy", repo / "clients" / "python" / "eagleshot_signing.py")
    mpy = _load("eagleshot_signing_mpy", repo / "clients" / "openmv" / "eagleshot_signing.py")
    return cpy, mpy


def test_signatures_match_for_image_upload(signers):
    cpy, mpy = signers
    args = dict(
        station_id="silvretta-glacier",
        secret_b64="abcdef0123456789-_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        method="POST",
        path="/v1/device/stations/silvretta-glacier/images",
        body=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        timestamp=1748000000,
        nonce_hex="0123456789abcdef0123456789abcdef",
    )
    assert cpy.sign_request(**args) == mpy.sign_request(**args)


def test_signatures_match_for_sensor_reading(signers):
    cpy, mpy = signers
    args = dict(
        station_id="alp-grimsel",
        secret_b64="ZDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTAx",
        method="POST",
        path="/v1/device/stations/alp-grimsel/sensor-readings",
        body=b'{"temperature":12.5,"humidity":78}',
        timestamp=1748123456,
        nonce_hex="ffffffffffffffffffffffffffffffff",
    )
    assert cpy.sign_request(**args) == mpy.sign_request(**args)


def test_hmac_implementation_matches_stdlib(signers):
    """The MicroPython port reimplements HMAC inline â€” verify it matches CPython's hmac."""
    import hmac
    import hashlib

    _, mpy = signers
    key = b"x" * 100  # > 64 bytes triggers key-shortening branch
    msg = b"sample message"
    expected = hmac.new(key, msg, hashlib.sha256).digest()
    assert mpy.hmac_sha256(key, msg) == expected


