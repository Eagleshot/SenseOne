"""Tests for main.add_validation_error_handler.

A 422 echoes the offending input back in its body. JSON bodies can carry
non-finite floats (``1e999`` parses to inf, ``NaN`` is accepted by the parser),
and Starlette renders JSON with allow_nan=False — without the handler, the echo
itself crashes the 422 into a 500.
"""

from fastapi.testclient import TestClient

from main import create_app


def _client(tmp_data_dir, monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://localhost:8080")
    return TestClient(create_app())


def _login_with_email_json(client: TestClient, raw_email_json: str):
    """POST /auth/login with a raw (non-str) email value to force a type error
    whose echoed input is that value."""
    return client.post(
        "/v1/auth/login",
        content=('{"email": %s, "password": "irrelevant"}' % raw_email_json).encode(),
        headers={"Content-Type": "application/json"},
    )


def test_inf_in_body_yields_422_with_stringified_echo(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)
    response = _login_with_email_json(client, "1e999")
    assert response.status_code == 422
    assert response.json()["detail"][0]["input"] == "inf"


def test_nan_in_body_yields_422_not_500(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)
    response = _login_with_email_json(client, "NaN")
    assert response.status_code == 422
    assert response.json()["detail"][0]["input"] == "nan"


def test_ordinary_validation_errors_are_unchanged(db, tmp_data_dir, monkeypatch):
    client = _client(tmp_data_dir, monkeypatch)
    response = _login_with_email_json(client, "12345")
    assert response.status_code == 422
    detail = response.json()["detail"]
    # Finite values pass through untouched, in the standard error shape.
    assert detail[0]["input"] == 12345
    assert detail[0]["loc"] == ["body", "email"]
