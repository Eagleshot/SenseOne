"""Helper-level tests for the OpenMV capture-cycle client.

The OpenMV firmware (``clients/openmv/main.py``) targets MicroPython and imports
board-only modules at the top level; ``tests._openmv`` stubs those so its pure
capture-cycle helpers can run under CPython. The firmware guards its run loop with
``if __name__ == "__main__"``, so importing the module only defines functions.
"""

from datetime import datetime

from tests._openmv import load_openmv_main


def _load_openmv_main(monkeypatch):
    return load_openmv_main(module_name="openmv_main_test", monkeypatch=monkeypatch)


def _epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def test_openmv_formats_capture_filename_from_utc_minute(monkeypatch):
    main = _load_openmv_main(monkeypatch)
    capture_seconds = _epoch("2026-05-24T14:30:05Z")

    # The capture minute is floored, then the name token is appended.
    assert main.round_down_to_minute(capture_seconds) == _epoch("2026-05-24T14:30:00Z")
    assert main.format_capture_filename(capture_seconds, "front") == "20260524_1430Z_front.jpg"


def test_openmv_date_math_is_independent_of_gmtime_epoch(monkeypatch):
    """Capture-cycle date math must not depend on the board's time.gmtime epoch.

    STM32 OpenMV cams use a 2000-01-01 epoch (not POSIX 1970). The helpers use
    pure integer math (``civil_from_days`` / ``unix_to_components``) and must
    ignore ``gmtime`` entirely; we break ``gmtime`` to prove it is never used.
    """
    main = _load_openmv_main(monkeypatch)

    def _no_gmtime(*_args, **_kwargs):
        raise AssertionError("capture date math must not call time.gmtime")

    monkeypatch.setattr(main.time, "gmtime", _no_gmtime, raising=False)

    assert main.unix_to_components(_epoch("2026-05-24T14:30:00Z")) == (2026, 5, 24, 14, 30, 0)
    assert main.format_capture_filename(_epoch("2026-05-24T14:30:05Z"), "front") == "20260524_1430Z_front.jpg"


def test_openmv_sanitizes_camera_name(monkeypatch):
    main = _load_openmv_main(monkeypatch)
    # Illegal filename characters collapse to '_'; an empty token falls back.
    assert main.sanitize_camera_name("Cam 1/front") == "Cam_1_front"
    assert main.sanitize_camera_name("   ") == "camera"


def test_openmv_capture_name_token_uses_config_name_and_stream(monkeypatch):
    main = _load_openmv_main(monkeypatch)

    # No STREAM configured -> just the server-provided name token.
    monkeypatch.setattr(main, "STREAM", "", raising=False)
    assert main.capture_name_token({"name": "zuerich"}) == "zuerich"

    # A STREAM is sanitized and appended after the name.
    monkeypatch.setattr(main, "STREAM", "thermal cam", raising=False)
    assert main.capture_name_token({"name": "zuerich"}) == "zuerich_thermal_cam"

    # Falls back to STATION_ID when the config carries no name (e.g. fetch failed).
    monkeypatch.setattr(main, "STREAM", "", raising=False)
    assert main.capture_name_token({}) == main.STATION_ID
