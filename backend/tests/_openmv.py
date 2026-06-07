"""Shared loader for the OpenMV firmware (clients/openmv/main.py) under CPython.

main.py targets MicroPython and imports board-only modules at the top level. We
stub those so importing it under CPython only defines its pure helpers + inline
signer (its capture loop is guarded by ``if __name__ == "__main__"``). Keeping the
stub list here means a new board-only import is updated in one place, not in every
test that loads the firmware.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

OPENMV_DIR = Path(__file__).resolve().parents[2] / "clients" / "openmv"


def _board_module_stubs() -> dict[str, SimpleNamespace]:
    # Fresh instances per call so monkeypatch-scoped installs don't share state.
    return {
        "sensor": SimpleNamespace(RGB565=1, HD=2),
        "network": SimpleNamespace(LAN=lambda *a, **k: None),
        "machine": SimpleNamespace(WDT=lambda *a, **k: None),
        "requests": SimpleNamespace(),
    }


def load_openmv_main(*, module_name: str = "openmv_main", monkeypatch=None):
    """Import clients/openmv/main.py under CPython and return the module.

    Pass ``monkeypatch`` to install the board-module stubs through it (removed
    after the test); otherwise they're set via ``setdefault`` for module-scoped use.
    ``module_name`` is the key the loaded module registers under in ``sys.modules``;
    give distinct names to load the firmware more than once in a session.
    """
    for name, stub in _board_module_stubs().items():
        if monkeypatch is not None:
            monkeypatch.setitem(sys.modules, name, stub)
        else:
            sys.modules.setdefault(name, stub)

    spec = importlib.util.spec_from_file_location(module_name, OPENMV_DIR / "main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
