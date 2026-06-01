"""Verify the OpenMV (MicroPython) device signer matches the server reference.

The device firmware in ``clients/openmv/main.py`` reimplements HMAC-SHA256 and
the v1 canonical signing string by hand. If it ever drifts from what the
server's ``station_hmac`` verifier expects, device-signed requests will be
rejected. Loading the OpenMV module into CPython and comparing its output
against the reference signer (which builds on the server's own canonical
string) catches any such drift.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import _signing as reference


def _load_openmv_main():
    repo = Path(__file__).resolve().parents[2]
    sys.modules.setdefault("sensor", SimpleNamespace(RGB565=1, VGA=2))
    sys.modules.setdefault("pyb", SimpleNamespace(UART=lambda *a, **kw: None))
    sys.modules.setdefault("machine", SimpleNamespace())
    spec = importlib.util.spec_from_file_location(
        "openmv_main_for_signer_test", repo / "clients" / "openmv" / "main.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["openmv_main_for_signer_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def openmv():
    return _load_openmv_main()


def test_signatures_match_for_image_upload(openmv):
    args = dict(
        station_id="silvretta-glacier",
        secret_b64="abcdef0123456789-_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        method="POST",
        path="/device/stations/silvretta-glacier/images",
        body=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        timestamp=1748000000,
        nonce_hex="0123456789abcdef0123456789abcdef",
    )
    assert openmv.sign_request(**args) == reference.sign_request(**args)


def test_signatures_match_for_sensor_reading(openmv):
    args = dict(
        station_id="alp-grimsel",
        secret_b64="ZDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTAx",
        method="POST",
        path="/device/stations/alp-grimsel/sensor-readings",
        body=b'{"temperature":12.5,"humidity":78}',
        timestamp=1748123456,
        nonce_hex="ffffffffffffffffffffffffffffffff",
    )
    assert openmv.sign_request(**args) == reference.sign_request(**args)


def test_signatures_match_for_empty_body_config_get(openmv):
    args = dict(
        station_id="alp-grimsel",
        secret_b64="ZDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTAx",
        method="GET",
        path="/device/stations/alp-grimsel/config",
        body=b"",
        timestamp=1748123456,
        nonce_hex="11111111111111111111111111111111",
    )
    assert openmv.sign_request(**args) == reference.sign_request(**args)


def test_hmac_implementation_matches_stdlib(openmv):
    """The MicroPython port reimplements HMAC inline — verify it matches CPython's hmac."""
    import hmac
    import hashlib

    key = b"x" * 100  # > 64 bytes triggers key-shortening branch
    msg = b"sample message"
    expected = hmac.new(key, msg, hashlib.sha256).digest()
    assert openmv.hmac_sha256(key, msg) == expected
