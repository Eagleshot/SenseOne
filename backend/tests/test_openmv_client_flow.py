"""Helper-level tests for the OpenMV capture cycle client."""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


def _load_openmv_main(monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    openmv_dir = repo / "clients" / "openmv"
    monkeypatch.syspath_prepend(str(openmv_dir))
    monkeypatch.setitem(sys.modules, "sensor", SimpleNamespace(RGB565=1, VGA=2))
    monkeypatch.setitem(sys.modules, "pyb", SimpleNamespace(UART=lambda *args, **kwargs: None))
    monkeypatch.setitem(sys.modules, "machine", SimpleNamespace())

    spec = importlib.util.spec_from_file_location("openmv_main_test", openmv_dir / "main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["openmv_main_test"] = module
    spec.loader.exec_module(module)
    return module


def _epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def test_openmv_formats_capture_filename_from_utc_minute(monkeypatch):
    main = _load_openmv_main(monkeypatch)
    capture_seconds = _epoch("2026-05-24T14:30:05Z")

    assert main.format_capture_filename(capture_seconds, "front") == "20260524_1430Z_front.jpg"
    assert main.format_iso_utc(main.round_down_to_minute(capture_seconds)) == "2026-05-24T14:30:00Z"


def test_openmv_adjusts_capture_ticks_to_server_utc(monkeypatch):
    main = _load_openmv_main(monkeypatch)
    monkeypatch.setattr(main.time, "ticks_diff", lambda current, previous: current - previous, raising=False)
    clock = main.ServerClock()
    clock._server_seconds_at_sync = _epoch("2026-05-24T14:30:10Z")
    clock._ticks_ms_at_sync = 10_000

    assert clock.unix_seconds_at_ticks(5_000) == _epoch("2026-05-24T14:30:05Z")


def test_openmv_date_math_is_independent_of_gmtime_epoch(monkeypatch):
    """Capture-cycle date math must not depend on the board's time.gmtime epoch.

    STM32 OpenMV cams use a 2000-01-01 epoch (not POSIX 1970). We feed gmtime the
    1970-epoch seconds it would receive on hardware, so a 2000-epoch gmtime would
    decode ~30 years late (2026 -> ~2056). The helpers must ignore gmtime entirely
    and still produce 2026.
    """
    main = _load_openmv_main(monkeypatch)

    epoch_offset = _epoch("2000-01-01T00:00:00Z")  # 1970->2000 epoch gap in seconds
    real_gmtime = main.time.gmtime

    def gmtime_2000(secs):  # emulate an STM32 board's 2000-epoch gmtime
        return real_gmtime(int(secs) + epoch_offset)

    monkeypatch.setattr(main.time, "gmtime", gmtime_2000, raising=False)

    capture_seconds = _epoch("2026-05-24T14:30:05Z")
    assert main.format_iso_utc(main.round_down_to_minute(capture_seconds)) == "2026-05-24T14:30:00Z"
    assert main.format_capture_filename(capture_seconds, "front") == "20260524_1430Z_front.jpg"

    config = {
        "stationStartMinute": 360,
        "stationStopMinute": 1200,
        "captureIntervalMinutes": 30,
        "useSunriseSunset": False,
    }
    assert main.compute_next_start(config, capture_seconds) == _epoch("2026-05-24T15:00:00Z")


def test_openmv_computes_next_start_inside_and_outside_window(monkeypatch):
    main = _load_openmv_main(monkeypatch)
    config = {
        "stationStartMinute": 360,
        "stationStopMinute": 1200,
        "captureIntervalMinutes": 30,
        "useSunriseSunset": False,
    }

    assert main.compute_next_start(config, _epoch("2026-05-24T05:30:00Z")) == _epoch("2026-05-24T06:00:00Z")
    assert main.compute_next_start(config, _epoch("2026-05-24T14:17:10Z")) == _epoch("2026-05-24T14:47:00Z")
    assert main.compute_next_start(config, _epoch("2026-05-24T21:00:00Z")) == _epoch("2026-05-25T06:00:00Z")


def test_openmv_includes_wake_reason_when_available(monkeypatch):
    main = _load_openmv_main(monkeypatch)
    main.machine = SimpleNamespace(reset_cause=lambda: "timer")

    assert main.read_sensor_data() == {"wakeReason": "timer"}


def test_openmv_deep_sleep_until_uses_synced_clock(monkeypatch):
    main = _load_openmv_main(monkeypatch)
    deepsleep_calls = []
    main.machine = SimpleNamespace(deepsleep=deepsleep_calls.append)
    clock = SimpleNamespace(now_unix_seconds=lambda: _epoch("2026-05-24T14:30:00Z"))

    main.deep_sleep_until(clock, _epoch("2026-05-24T15:00:00Z"))

    assert deepsleep_calls == [30 * 60 * 1000]
