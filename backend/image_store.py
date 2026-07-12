"""Image blob storage seam.

The control-plane DB stores each image's ``storage_key``; this module owns what
a key means physically. ``LocalDiskImageStore`` keeps blobs on the local disk
under the data dir. An object-store implementation (e.g. Cloudflare R2) can
replace it behind the same methods without touching the routes — serving would
then redirect/stream instead of using ``path()``, and the free-disk guard
becomes a no-op (``free_bytes`` returning None already means "cannot check").
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from settings import get_data_dir


def station_image_key(public_id: str, filename: str) -> str:
    """Canonical storage key for a station capture (also persisted on the DB row)."""
    return f"{public_id}/images/{filename}"


class LocalDiskImageStore:
    """Blob store backed by a local directory; keys are paths relative to the root."""

    def __init__(self, root: Path):
        self._root = root.resolve()

    def path(self, key: str) -> Path:
        """Local filesystem path for a key (local-store specific; used to serve files).

        Refuses keys that resolve outside the root, so a hostile key can never
        escape the data dir regardless of what the caller validated.
        """
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"Storage key escapes the data dir: {key!r}")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def delete_prefix(self, key_prefix: str) -> None:
        """Remove every blob under a key prefix (locally: the directory tree).

        Used when a station is deleted: its blobs all live under
        ``<public_id>/``. Missing prefixes are a no-op.
        """
        shutil.rmtree(self.path(key_prefix), ignore_errors=True)

    def free_bytes(self) -> int | None:
        """Free space on the storage volume, or None when it cannot be determined."""
        try:
            return shutil.disk_usage(self._root).free
        except OSError as exc:
            logging.warning("Could not check free disk space at %s: %s", self._root, exc)
            return None


def get_image_store() -> LocalDiskImageStore:
    """The image store for the configured data dir (fresh per call, like get_settings)."""
    return LocalDiskImageStore(get_data_dir())
