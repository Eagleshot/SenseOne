"""Tests for shared station access checks (SQLite-backed)."""

import uuid
from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from station_access import (
    can_edit_station,
    can_view_station,
    require_station_edit,
    require_station_view,
)
from tests import _db


@dataclass(frozen=True)
class AccessUser:
    owner_id: str
    is_admin: bool = False


def test_public_station_is_visible_to_anonymous(db):
    _db.create_station_row("pub", is_public=True)
    assert can_view_station("pub", None) is True


def test_private_station_is_hidden_from_anonymous(db):
    _db.create_station_row("priv", is_public=False)
    with pytest.raises(HTTPException) as exc:
        require_station_view("priv", None)
    assert exc.value.status_code == 404


def test_private_station_owner_can_edit(db):
    owner = _db.create_owner("owner@example.com")
    _db.create_station_row("priv", is_public=False, owner_id=owner.owner_id)
    require_station_edit("priv", AccessUser(owner.owner_id))


def test_private_station_non_owner_gets_404_not_403(db):
    # A non-owner can't view a private station, so edit hides its existence (404)
    # rather than confirming it with a 403.
    owner = _db.create_owner("owner@example.com")
    _db.create_station_row("priv", is_public=False, owner_id=owner.owner_id)
    with pytest.raises(HTTPException) as exc:
        require_station_edit("priv", AccessUser(str(uuid.uuid4())))
    assert exc.value.status_code == 404


def test_public_station_non_owner_gets_403(db):
    # A public station's existence is already known, so a non-owner editor gets 403.
    owner = _db.create_owner("owner@example.com")
    _db.create_station_row("pub", is_public=True, owner_id=owner.owner_id)
    with pytest.raises(HTTPException) as exc:
        require_station_edit("pub", AccessUser(str(uuid.uuid4())))
    assert exc.value.status_code == 403


def test_admin_can_edit_any_station(db):
    _db.create_station_row("priv", is_public=False)
    require_station_edit("priv", AccessUser(str(uuid.uuid4()), is_admin=True))


def test_can_edit_station_owner_admin_and_outsider(db):
    owner = _db.create_owner("owner@example.com")
    _db.create_station_row("pub", is_public=True, owner_id=owner.owner_id)

    assert can_edit_station("pub", AccessUser(owner.owner_id)) is True
    assert can_edit_station("pub", AccessUser(str(uuid.uuid4()), is_admin=True)) is True
    assert can_edit_station("pub", AccessUser(str(uuid.uuid4()))) is False
    assert can_edit_station("pub", None) is False
