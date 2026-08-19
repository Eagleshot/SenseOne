"""Tests for authentication."""

from datetime import datetime, timedelta, timezone

from auth import (
    AUTH_TOKEN_TTL_SECONDS,
    _hash_session_token,
    _user_for_token,
    create_session,
    remove_session,
)
from tests import _db


class TestSessionManagement:
    """Sessions are stored (hashed) in the control DB, so these need the db fixture.

    The per-request lookup (session_user) joins the session to its user row, so
    each test that expects a resolved session first creates that user.
    """

    def test_create_session_roundtrip(self, db):
        _db.create_owner("testuser@example.com")
        token, ttl = create_session("testuser@example.com")

        assert isinstance(token, str)
        assert len(token) > 20  # Should be reasonably long
        assert ttl == AUTH_TOKEN_TTL_SECONDS
        assert _user_for_token(token).email == "testuser@example.com"

    def test_token_is_stored_hashed_not_plaintext(self, db):
        from db import user_repo

        _db.create_owner("testuser@example.com")
        token, _ = create_session("testuser@example.com")
        # The raw token is not a valid key; only its hash is.
        assert user_repo.session_user(token) is None
        assert user_repo.session_user(_hash_session_token(token)).email == "testuser@example.com"

    def test_remove_session_invalidates_token(self, db):
        _db.create_owner("testuser@example.com")
        token, _ = create_session("testuser@example.com")
        remove_session(token)
        assert _user_for_token(token) is None

    def test_expired_session_is_invalid_and_pruned(self, db):
        from db import user_repo

        _db.create_owner("testuser@example.com")
        user_repo.session_create(
            _hash_session_token("expired_token"),
            "testuser@example.com",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert _user_for_token("expired_token") is None
        user_repo.sessions_prune_expired()
        assert user_repo.session_user(_hash_session_token("expired_token")) is None

    def test_prune_keeps_valid_sessions(self, db):
        from db import user_repo

        _db.create_owner("testuser@example.com")
        token, _ = create_session("testuser@example.com")
        user_repo.sessions_prune_expired()
        assert _user_for_token(token).email == "testuser@example.com"


class TestCredentialVerification:
    """Test credential verification."""

    def test_hash_secret_roundtrip(self):
        """A hashed secret should verify against its plaintext."""
        from security import hash_secret, verify_secret

        stored = hash_secret("correct-horse-battery-staple")
        assert verify_secret("correct-horse-battery-staple", stored)
        assert not verify_secret("wrong-password", stored)
        assert not verify_secret("correct-horse-battery-staple", None)

    def test_secret_verification_is_timing_safe(self):
        """verify_secret must use hmac.compare_digest under the hood."""
        import inspect
        from security import verify_secret

        source = inspect.getsource(verify_secret)
        assert "compare_digest" in source


class TestUserEnumerationTiming:
    """Unknown-email logins must spend the same PBKDF2 time as known-user failures."""

    def test_unknown_user_verifies_against_real_dummy_hash(self, db, monkeypatch):
        from db import user_repo
        from security import dummy_password_hash

        captured = {}
        real_verify = user_repo.verify_secret

        def spy(secret, stored):
            captured["stored"] = stored
            return real_verify(secret, stored)

        monkeypatch.setattr(user_repo, "verify_secret", spy)
        # No user exists, so this is the unknown-email path; it must still run a
        # real PBKDF2 against the dummy hash (not short-circuit on None).
        assert user_repo.user_authenticate("ghost@example.com", "some-long-password") is None
        assert captured["stored"] == dummy_password_hash()

    def test_dummy_hash_is_a_real_pbkdf2_hash(self):
        from security import dummy_password_hash, verify_secret

        # A valid stored hash that no real password should match by accident.
        assert dummy_password_hash().startswith("$pbkdf2_sha256$")
        assert not verify_secret("some-long-password", dummy_password_hash())


class TestThrottleClientIp:
    """Behind the Cloudflare Tunnel the TCP peer is always cloudflared, so the
    throttle must key on CF-Connecting-IP when present."""

    @staticmethod
    def _request(headers: dict[str, str], client_host: str | None = "127.0.0.1"):
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/auth/login",
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }
        if client_host is not None:
            scope["client"] = (client_host, 40000)
        return Request(scope)

    def test_prefers_cf_connecting_ip(self):
        from auth import throttle_client_ip

        request = self._request({"CF-Connecting-IP": "203.0.113.7"})
        assert throttle_client_ip(request) == "203.0.113.7"

    def test_falls_back_to_socket_peer_without_header(self):
        from auth import throttle_client_ip

        assert throttle_client_ip(self._request({})) == "127.0.0.1"
        assert throttle_client_ip(self._request({"CF-Connecting-IP": "  "})) == "127.0.0.1"
        assert throttle_client_ip(self._request({}, client_host=None)) == "unknown"


def test_auth_cookie_secure_tracks_require_https(monkeypatch):
    """The session cookie's Secure flag follows APP_REQUIRE_HTTPS so it isn't dropped in HTTP dev."""
    from auth import auth_cookie_secure

    monkeypatch.setenv("APP_REQUIRE_HTTPS", "true")
    assert auth_cookie_secure() is True
    monkeypatch.setenv("APP_REQUIRE_HTTPS", "false")
    assert auth_cookie_secure() is False
    monkeypatch.delenv("APP_REQUIRE_HTTPS", raising=False)
    assert auth_cookie_secure() is False


