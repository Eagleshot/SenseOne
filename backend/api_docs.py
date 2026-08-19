"""Public OpenAPI metadata for the Eagleshot API.

Keep this module limited to information an API caller needs. Operational and
security implementation details belong in code comments and deployment docs,
not in the public schema.
"""

from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from constants import AUTH_COOKIE_NAME


PUBLIC_API_DESCRIPTION = (
    "Eagleshot's HTTP API for station browsing, management, weather data, and "
    "signed device ingestion. Browser sessions use the login endpoint; device "
    "requests use the HMAC headers described under **Device ingestion**."
)

PUBLIC_OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "System",
        "description": "Service availability and clock endpoints.",
    },
    {
        "name": "Auth",
        "description": (
            "Create and inspect a user session. Browsers use the session cookie; "
            "non-browser clients may send the same token as a bearer token."
        ),
    },
    {
        "name": "Stations",
        "description": "Browse stations and manage station-owned data and settings.",
    },
    {
        "name": "Weather",
        "description": "Weather observations, forecasts, geocoding, and map overlays.",
    },
    {
        "name": "Device ingestion",
        "description": (
            "Device requests require `X-Station-Id`, `X-Timestamp`, `X-Nonce`, and "
            "`X-Signature`. Compute `X-Signature` as `v1=<hex HMAC-SHA256>` over "
            "the following newline-separated UTF-8 string, using the station's "
            "base64url-decoded device secret as the key:\n\n"
            "```text\n"
            "v1\n"
            "<station_id>\n"
            "<unix_timestamp>\n"
            "<nonce>\n"
            "<UPPERCASE_METHOD>\n"
            "<request_path_without_query>\n"
            "<lowercase_sha256_of_body>\n"
            "<x_filename_or_empty>\n"
            "```\n\n"
            "`X-Timestamp` must be within 300 seconds of the server clock. "
            "`X-Nonce` must be fresh hexadecimal text of at least 16 characters. "
            "For image uploads, the exact `X-Filename` value is signed; other "
            "requests use an empty final line."
        ),
    },
]


def error_response(description: str) -> dict[str, Any]:
    """A concise JSON error response for route decorators."""
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"detail": {}},
                    "required": ["detail"],
                }
            }
        },
    }


RAW_IMAGE_REQUEST_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            media_type: {"schema": {"type": "string", "format": "binary"}}
            for media_type in ("image/jpeg", "image/png", "image/webp")
        },
    }
}

IMAGE_RESPONSE_CONTENT: dict[str, Any] = {
    media_type: {"schema": {"type": "string", "format": "binary"}}
    for media_type in ("image/jpeg", "image/png", "image/webp")
}

PNG_RESPONSE_CONTENT: dict[str, Any] = {
    "image/png": {"schema": {"type": "string", "format": "binary"}}
}

SENSOR_INGESTION_EXAMPLE: dict[str, Any] = {
    "timestamp": "2026-07-21T08:15:00Z",
    "nextStart": "2026-07-21T08:45:00Z",
    "firmwareVersion": "camera-1.0",
    "readings": [
        {
            "channel": "default",
            "temperature": 7.4,
            "battery": 92,
        }
    ],
}

CURRENT_WEATHER_RESPONSE: dict[str, Any] = {
    "description": "Current metric weather data. Additional upstream fields may be present.",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "main": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "temp": {"type": "number"},
                            "feels_like": {"type": "number"},
                            "humidity": {"type": "number"},
                            "pressure": {"type": "number"},
                        },
                    },
                    "wind": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "speed": {"type": "number"},
                            "deg": {"type": "number"},
                        },
                    },
                    "weather": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "main": {"type": "string"},
                                "description": {"type": "string"},
                                "icon": {"type": "string"},
                            },
                        },
                    },
                    "visibility": {"type": "integer"},
                    "sys": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "sunrise": {"type": "integer"},
                            "sunset": {"type": "integer"},
                        },
                    },
                    "dt": {"type": "integer"},
                    "timezone": {"type": "integer"},
                    "name": {"type": "string"},
                },
            },
            "example": {
                "main": {"temp": 7.4, "feels_like": 5.8, "humidity": 74, "pressure": 1018},
                "wind": {"speed": 2.3, "deg": 240},
                "weather": [{"main": "Clouds", "description": "broken clouds", "icon": "04d"}],
                "visibility": 10000,
                "sys": {"sunrise": 1784606400, "sunset": 1784661600},
                "dt": 1784635200,
                "timezone": 7200,
                "name": "Davos",
            },
        }
    },
}

FORECAST_WEATHER_RESPONSE: dict[str, Any] = {
    "description": "Metric forecast entries. Additional upstream fields may be present.",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "dt": {"type": "integer"},
                                "main": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "temp": {"type": "number"},
                                        "temp_min": {"type": "number"},
                                        "temp_max": {"type": "number"},
                                    },
                                },
                                "weather": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": True,
                                        "properties": {"icon": {"type": "string"}},
                                    },
                                },
                            },
                        },
                    },
                    "city": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {"timezone": {"type": "integer"}},
                    },
                },
            },
            "example": {
                "list": [
                    {
                        "dt": 1784635200,
                        "main": {"temp": 7.4, "temp_min": 6.9, "temp_max": 7.8},
                        "weather": [{"icon": "04d"}],
                    }
                ],
                "city": {"timezone": 7200},
            },
        }
    },
}


OperationKey = tuple[str, str]

_PUBLIC_OPERATIONS: set[OperationKey] = {
    ("get", "/"),
    ("get", "/health"),
    ("get", "/clock"),
    ("post", "/v1/auth/login"),
    ("get", "/v1/weather/map/{layer}/{z}/{x}/{y}"),
}

_OPTIONAL_SESSION_OPERATIONS: set[OperationKey] = {
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

_REQUIRED_SESSION_OPERATIONS: set[OperationKey] = {
    ("get", "/v1/auth/me"),
    ("post", "/v1/stations"),
    ("post", "/v1/stations/{station_id}/rotate-device-secret"),
    ("delete", "/v1/stations/{station_id}"),
    ("get", "/v1/stations/{station_id}/config"),
    ("put", "/v1/stations/{station_id}/config"),
    ("get", "/v1/geo/reverse"),
}

_DEVICE_HMAC_OPERATIONS: set[OperationKey] = {
    ("get", "/v1/ingest/stations/{station_id}/config"),
    ("post", "/v1/ingest/stations/{station_id}/images"),
    ("post", "/v1/ingest/stations/{station_id}/data"),
}

_ALL_DOCUMENTED_OPERATIONS = (
    _PUBLIC_OPERATIONS
    | _OPTIONAL_SESSION_OPERATIONS
    | _REQUIRED_SESSION_OPERATIONS
    | _DEVICE_HMAC_OPERATIONS
)


def _operation_keys(schema: dict[str, Any]) -> set[OperationKey]:
    methods = {"get", "post", "put", "delete", "patch"}
    return {
        (method, path)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method in methods
    }


def _set_security(schema: dict[str, Any], operations: Iterable[OperationKey], security: list[dict[str, Any]]) -> None:
    for method, path in operations:
        schema["paths"][path][method]["security"] = security


def configure_public_openapi(app: FastAPI) -> None:
    """Install the public, consumer-focused OpenAPI schema builder."""

    def public_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )

        actual_operations = _operation_keys(schema)
        if actual_operations != _ALL_DOCUMENTED_OPERATIONS:
            missing = sorted(actual_operations - _ALL_DOCUMENTED_OPERATIONS)
            stale = sorted(_ALL_DOCUMENTED_OPERATIONS - actual_operations)
            raise RuntimeError(
                f"OpenAPI authentication classification is incomplete: missing={missing}, stale={stale}"
            )

        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schemes.pop("HTTPBearer", None)
        schemes.update(
            {
                "sessionCookie": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": AUTH_COOKIE_NAME,
                    "description": "Session cookie returned by POST /v1/auth/login.",
                },
                "sessionBearer": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Session token sent as Authorization: Bearer <token>.",
                },
                "deviceStationId": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Station-Id",
                    "description": "Stable station id; must match the path parameter.",
                },
                "deviceTimestamp": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Timestamp",
                    "description": "Current Unix timestamp in seconds.",
                },
                "deviceNonce": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Nonce",
                    "description": "Fresh hexadecimal nonce of at least 16 characters.",
                },
                "deviceSignature": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Signature",
                    "description": "v1 HMAC-SHA256 signature described in the Device ingestion section.",
                },
            }
        )

        session_security = [{"sessionCookie": []}, {"sessionBearer": []}]
        _set_security(schema, _PUBLIC_OPERATIONS, [])
        _set_security(schema, _OPTIONAL_SESSION_OPERATIONS, [{}, *session_security])
        _set_security(schema, _REQUIRED_SESSION_OPERATIONS, session_security)
        _set_security(
            schema,
            _DEVICE_HMAC_OPERATIONS,
            [
                {
                    "deviceStationId": [],
                    "deviceTimestamp": [],
                    "deviceNonce": [],
                    "deviceSignature": [],
                }
            ],
        )

        app.openapi_schema = schema
        return schema

    app.openapi = public_openapi
