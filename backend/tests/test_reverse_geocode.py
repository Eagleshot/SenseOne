"""Tests for the reverse-geocoding proxy (coordinates -> place name / country).

The upstream OpenWeather client is stubbed, so no network or API quota is
needed; coordinates differ per test because results are cached process-wide.
"""

import asyncio

import pytest
from fastapi import HTTPException

import httpx

from routes import weather as weather_routes


class _StubResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _StubClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = 0

    async def get(self, url, params=None):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._response


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")


def _call(lat, lon):
    return asyncio.run(weather_routes.reverse_geocode(lat=lat, lon=lon, user=object()))


def test_maps_first_upstream_hit_to_name_and_country(api_key, monkeypatch):
    stub = _StubClient(
        response=_StubResponse(payload=[{"name": "Davos", "country": "CH", "state": "Grisons"}])
    )
    monkeypatch.setattr(weather_routes, "_get_openweather_client", lambda: stub)

    assert _call(46.8, 9.83) == {"name": "Davos", "countryCode": "CH", "state": "Grisons"}


def test_empty_upstream_result_returns_nulls(api_key, monkeypatch):
    stub = _StubClient(response=_StubResponse(payload=[]))
    monkeypatch.setattr(weather_routes, "_get_openweather_client", lambda: stub)

    assert _call(0.001, -140.0) == {"name": None, "countryCode": None, "state": None}


def test_result_is_cached(api_key, monkeypatch):
    stub = _StubClient(response=_StubResponse(payload=[{"name": "Zermatt", "country": "CH"}]))
    monkeypatch.setattr(weather_routes, "_get_openweather_client", lambda: stub)

    first = _call(46.02, 7.75)
    second = _call(46.02, 7.75)
    assert first == second
    assert stub.calls == 1


def test_upstream_error_surfaces_as_502(api_key, monkeypatch):
    stub = _StubClient(error=httpx.RequestError("boom"))
    monkeypatch.setattr(weather_routes, "_get_openweather_client", lambda: stub)

    with pytest.raises(HTTPException) as exc:
        _call(10.0, 10.0)
    assert exc.value.status_code == 502


def test_upstream_http_error_surfaces_as_502(api_key, monkeypatch):
    stub = _StubClient(response=_StubResponse(status_code=429, payload={}))
    monkeypatch.setattr(weather_routes, "_get_openweather_client", lambda: stub)

    with pytest.raises(HTTPException) as exc:
        _call(20.0, 20.0)
    assert exc.value.status_code == 502
