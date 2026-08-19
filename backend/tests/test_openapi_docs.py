"""Contract tests for the public FastAPI API reference."""

import re
from typing import Any

import pytest

from api_docs import SENSOR_INGESTION_EXAMPLE
from main import create_app
from models import SensorReadingRequest


OperationKey = tuple[str, str]

PUBLIC: set[OperationKey] = {
    ("get", "/"),
    ("get", "/health"),
    ("get", "/clock"),
    ("post", "/v1/auth/login"),
    ("get", "/v1/weather/map/{layer}/{z}/{x}/{y}"),
}

OPTIONAL_SESSION: set[OperationKey] = {
    ("post", "/v1/auth/logout"),
    ("get", "/v1/stations"),
    ("get", "/v1/stations/{station_id}"),
    ("get", "/v1/stations/{station_id}/image-captures"),
    ("get", "/v1/stations/{station_id}/images/{filename}"),
    ("get", "/v1/stations/{station_id}/data"),
    ("get", "/v1/stations/{station_id}/readings"),
    ("get", "/v1/stations/{station_id}/weather/current"),
    ("get", "/v1/stations/{station_id}/weather/forecast"),
}

REQUIRED_SESSION: set[OperationKey] = {
    ("get", "/v1/auth/me"),
    ("post", "/v1/stations"),
    ("post", "/v1/stations/{station_id}/rotate-device-secret"),
    ("delete", "/v1/stations/{station_id}"),
    ("get", "/v1/stations/{station_id}/config"),
    ("put", "/v1/stations/{station_id}/config"),
    ("get", "/v1/geo/reverse"),
}

DEVICE_HMAC: set[OperationKey] = {
    ("get", "/v1/ingest/stations/{station_id}/config"),
    ("post", "/v1/ingest/stations/{station_id}/images"),
    ("post", "/v1/ingest/stations/{station_id}/data"),
}

ALL_OPERATIONS = PUBLIC | OPTIONAL_SESSION | REQUIRED_SESSION | DEVICE_HMAC


@pytest.fixture
def schema(db, tmp_data_dir, monkeypatch) -> dict[str, Any]:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    return create_app().openapi()


def operation(schema: dict[str, Any], key: OperationKey) -> dict[str, Any]:
    method, path = key
    return schema["paths"][path][method]


def test_all_operations_have_minimal_reference_metadata(schema):
    methods = {"get", "post", "put", "delete", "patch"}
    actual = {
        (method, path)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method in methods
    }

    assert actual == ALL_OPERATIONS
    assert len(actual) == 24
    assert [tag["name"] for tag in schema["tags"]] == [
        "System",
        "Auth",
        "Stations",
        "Weather",
        "Device ingestion",
    ]

    for key in actual:
        documented = operation(schema, key)
        assert documented["summary"].strip()
        assert documented["description"].strip()
        assert len(documented["tags"]) == 1
        assert any(code.startswith("2") for code in documented["responses"])


def test_authentication_metadata_matches_runtime_contract(schema):
    schemes = schema["components"]["securitySchemes"]
    assert schemes["sessionCookie"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "eagleshot_session",
        "description": "Session cookie returned by POST /v1/auth/login.",
    }
    assert schemes["sessionBearer"]["type"] == "http"
    assert schemes["sessionBearer"]["scheme"] == "bearer"

    expected_hmac_schemes = {
        "deviceStationId": "X-Station-Id",
        "deviceTimestamp": "X-Timestamp",
        "deviceNonce": "X-Nonce",
        "deviceSignature": "X-Signature",
    }
    for name, header in expected_hmac_schemes.items():
        assert schemes[name]["type"] == "apiKey"
        assert schemes[name]["in"] == "header"
        assert schemes[name]["name"] == header

    session = [{"sessionCookie": []}, {"sessionBearer": []}]
    hmac = [{name: [] for name in expected_hmac_schemes}]
    for key in PUBLIC:
        assert operation(schema, key)["security"] == []
    for key in OPTIONAL_SESSION:
        assert operation(schema, key)["security"] == [{}, *session]
    for key in REQUIRED_SESSION:
        assert operation(schema, key)["security"] == session
    for key in DEVICE_HMAC:
        assert operation(schema, key)["security"] == hmac


def test_request_examples_and_media_types(schema):
    login = operation(schema, ("post", "/v1/auth/login"))
    assert "application/json" in login["requestBody"]["content"]
    assert "application/json" in login["responses"]["200"]["content"]

    image_upload = operation(
        schema, ("post", "/v1/ingest/stations/{station_id}/images")
    )
    assert set(image_upload["requestBody"]["content"]) == {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
    for media_type in ("image/jpeg", "image/png", "image/webp"):
        assert image_upload["requestBody"]["content"][media_type]["schema"] == {
            "type": "string",
            "format": "binary",
        }

    image_fetch = operation(
        schema, ("get", "/v1/stations/{station_id}/images/{filename}")
    )
    assert set(image_fetch["responses"]["200"]["content"]) == {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
    for media_type in ("image/jpeg", "image/png", "image/webp"):
        assert image_fetch["responses"]["200"]["content"][media_type]["schema"] == {
            "type": "string",
            "format": "binary",
        }

    tile = operation(schema, ("get", "/v1/weather/map/{layer}/{z}/{x}/{y}"))
    assert tile["responses"]["200"]["content"] == {
        "image/png": {"schema": {"type": "string", "format": "binary"}}
    }

    ingestion = operation(
        schema, ("post", "/v1/ingest/stations/{station_id}/data")
    )
    documented_example = ingestion["requestBody"]["content"]["application/json"][
        "example"
    ]
    assert documented_example == SENSOR_INGESTION_EXAMPLE
    assert SensorReadingRequest.model_validate(documented_example).readings

    current = operation(
        schema, ("get", "/v1/stations/{station_id}/weather/current")
    )["responses"]["200"]["content"]["application/json"]["schema"]
    assert current["additionalProperties"] is True
    assert {"temp", "feels_like", "humidity", "pressure"} <= set(
        current["properties"]["main"]["properties"]
    )

    forecast = operation(
        schema, ("get", "/v1/stations/{station_id}/weather/forecast")
    )["responses"]["200"]["content"]["application/json"]["schema"]
    assert forecast["additionalProperties"] is True
    forecast_item = forecast["properties"]["list"]["items"]
    assert {"dt", "main", "weather"} <= set(forecast_item["properties"])


def _descriptions(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "description" and isinstance(item, str):
                yield item
            else:
                yield from _descriptions(item)
    elif isinstance(value, list):
        for item in value:
            yield from _descriptions(item)


def test_public_descriptions_do_not_expose_internal_posture(schema):
    public_text = "\n".join(_descriptions(schema))
    prohibited = re.compile(
        r"throttl|brute[- ]?force|vulnerab|APP_|OPENWEATHER_API_KEY|database|"
        r"sqlite|worker|process topology|cache|free disk|storage floor|"
        r"encrypted at rest|station_device_secrets|repository",
        re.IGNORECASE,
    )
    assert prohibited.search(public_text) is None
