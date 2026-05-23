"""Tests for shared station access checks."""

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from config import write_station_config, write_station_meta
from models import AppConfig
from station_access import can_view_station, require_station_edit, require_station_view


@dataclass(frozen=True)
class AccessUser:
    username: str
    is_admin: bool = False


def test_public_station_is_visible_to_anonymous(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    write_station_config(data_dir, station_id, AppConfig(is_public=True))

    assert can_view_station(station_id, None) is True


def test_private_station_is_hidden_from_anonymous(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    write_station_config(data_dir, station_id, AppConfig(is_public=False))

    with pytest.raises(HTTPException) as exc:
        require_station_view(station_id, None)

    assert exc.value.status_code == 404


def test_private_station_owner_can_edit(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    write_station_config(data_dir, station_id, AppConfig(is_public=False))
    write_station_meta(data_dir, station_id, owner="owner")

    require_station_edit(station_id, AccessUser("owner"))


def test_private_station_non_owner_cannot_edit(setup_station_dir, monkeypatch):
    data_dir, station_id = setup_station_dir
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    write_station_config(data_dir, station_id, AppConfig(is_public=False))
    write_station_meta(data_dir, station_id, owner="owner")

    with pytest.raises(HTTPException) as exc:
        require_station_edit(station_id, AccessUser("other"))

    assert exc.value.status_code == 403


