"""Tests for the weather tile proxy's coordinate validation.

The endpoint is unauthenticated, so out-of-range tiles must be rejected before
any upstream OpenWeather call (each distinct key would otherwise burn quota).
Validation happens before the upstream fetch, so no network/API key is needed.
"""

import asyncio

import pytest
from fastapi import HTTPException

from routes.weather import MAX_WEATHER_TILE_ZOOM, get_weather_map_tile


@pytest.mark.parametrize(
    ("z", "x", "y"),
    [
        (MAX_WEATHER_TILE_ZOOM + 1, 0, 0),  # zoom above the cap
        (-1, 0, 0),  # negative zoom
        (5, 32, 0),  # x == 2**z (one past the last valid index)
        (5, 0, 32),  # y == 2**z
        (5, -1, 0),  # negative x
        (5, 0, -1),  # negative y
    ],
)
def test_out_of_range_tile_is_rejected(z, x, y):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_weather_map_tile("clouds_new", z, x, y))
    assert exc.value.status_code == 404


def test_unknown_layer_is_rejected():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_weather_map_tile("not_a_layer", 1, 0, 0))
    assert exc.value.status_code == 404
