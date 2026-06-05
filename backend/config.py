"""Data directory resolution.

Returns the directory where image blobs and the replay-nonce sqlite DB are
written. Station metadata, config, ownership, and device secrets live in the
SQLite control-plane DB (see db/), which by default also sits in this directory.
"""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """Get data directory from environment (used for image blobs + nonce DB)."""
    base_dir = Path(__file__).resolve().parent
    return Path(os.getenv("APP_DATA_DIR") or (base_dir / "data")).resolve()
