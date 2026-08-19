"""Tests for the control-plane engine factory."""

import pytest


def test_non_sqlite_database_url_is_rejected(monkeypatch):
    """The data layer is SQLite-only (sqlite-dialect upserts); anything else
    must fail the boot with a clear error, not die later mid-request."""
    import db.session as session_module

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/eagleshot")
    monkeypatch.setattr(session_module, "_engine", None)
    monkeypatch.setattr(session_module, "_sessionmaker", None)
    with pytest.raises(RuntimeError, match="sqlite"):
        session_module.get_engine()
