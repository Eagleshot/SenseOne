"""Verify the device signers match the server reference.

The OpenMV firmware (``clients/openmv/``) and the CPython client
(``clients/python/``) each reimplement HMAC-SHA256 and the v1 canonical signing
string outside the backend. If either drifts from what the server's
``station_hmac`` verifier expects, device-signed requests will be rejected.
Loading the client modules into CPython and comparing their output against the
reference signer (which builds on the server's own canonical string) catches
any such drift.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import _signing as reference


REPO = Path(__file__).resolve().parents[2]
OPENMV_DIR = REPO / "clients" / "openmv"
PYTHON_CLIENT = REPO / "clients" / "python" / "eagleshot.py"


def _load_from_path(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_openmv_main():
    sys.modules.setdefault("sensor", SimpleNamespace(RGB565=1, VGA=2))
    sys.modules.setdefault("pyb", SimpleNamespace(UART=lambda *a, **kw: None))
    sys.modules.setdefault("machine", SimpleNamespace())
    # main.py does a bare `import eagleshot_signing`; on the board that module
    # sits next to it, so put its directory on sys.path for the import to
    # resolve here too.
    if str(OPENMV_DIR) not in sys.path:
        sys.path.insert(0, str(OPENMV_DIR))
    return _load_from_path("openmv_main_for_signer_test", OPENMV_DIR / "main.py")


@pytest.fixture(scope="module")
def openmv():
    return _load_openmv_main()


@pytest.fixture(scope="module")
def openmv_signer(openmv):
    # Importing main.py pulled in the shared signer that ships beside it.
    return sys.modules["eagleshot_signing"]


@pytest.fixture(scope="module")
def python_signer():
    return _load_from_path("eagleshot_signing_cpython_client", PYTHON_CLIENT)


# Fixed (deterministic timestamp + nonce) inputs covering the three device calls.
_IMAGE_UPLOAD = dict(
    station_id="silvretta-glacier",
    secret_b64="abcdef0123456789-_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    method="POST",
    path="/v1/ingest/stations/silvretta-glacier/images",
    body=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
    timestamp=1748000000,
    nonce_hex="0123456789abcdef0123456789abcdef",
)
_SENSOR_READING = dict(
    station_id="alp-grimsel",
    secret_b64="ZDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTAx",
    method="POST",
    path="/v1/ingest/stations/alp-grimsel/data",
    body=b'{"readings":[{"temperature":12.5,"humidity":78}]}',
    timestamp=1748123456,
    nonce_hex="ffffffffffffffffffffffffffffffff",
)
_CONFIG_GET = dict(
    station_id="alp-grimsel",
    secret_b64="ZDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTAx",
    method="GET",
    path="/v1/ingest/stations/alp-grimsel/config",
    body=b"",
    timestamp=1748123456,
    nonce_hex="11111111111111111111111111111111",
)
_CASES = [_IMAGE_UPLOAD, _SENSOR_READING, _CONFIG_GET]
_CASE_IDS = ["image-upload", "sensor-reading", "config-get"]


@pytest.mark.parametrize("args", _CASES, ids=_CASE_IDS)
def test_openmv_signatures_match_reference(openmv, args):
    assert openmv.sign_request(**args) == reference.sign_request(**args)


@pytest.mark.parametrize("args", _CASES, ids=_CASE_IDS)
def test_python_client_signatures_match_reference(python_signer, args):
    assert python_signer.sign_request(**args) == reference.sign_request(**args)


def test_openmv_hmac_implementation_matches_stdlib(openmv_signer):
    """The MicroPython port reimplements HMAC inline — verify it matches CPython's hmac."""
    import hmac
    import hashlib

    key = b"x" * 100  # > 64 bytes triggers key-shortening branch
    msg = b"sample message"
    expected = hmac.new(key, msg, hashlib.sha256).digest()
    assert openmv_signer.hmac_sha256(key, msg) == expected
