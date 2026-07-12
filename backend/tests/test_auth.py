"""Tests for authentication."""

from datetime import datetime, timedelta, timezone

from auth import (
    AUTH_TOKEN_TTL_SECONDS,
    _hash_session_token,
    _validate_session_token,
    create_session,
    prune_expired_sessions,
    remove_session,
)


class TestSessionManagement:
    """Sessions are stored (hashed) in the control DB, so these need the db fixture."""

    def test_create_session_roundtrip(self, db):
        token, ttl = create_session("testuser@example.com")

        assert isinstance(token, str)
        assert len(token) > 20  # Should be reasonably long
        assert ttl == AUTH_TOKEN_TTL_SECONDS
        assert _validate_session_token(token) == "testuser@example.com"

    def test_token_is_stored_hashed_not_plaintext(self, db):
        from db import sqlite_repo

        token, _ = create_session("testuser@example.com")
        # The raw token is not a valid key; only its hash is.
        assert sqlite_repo.session_email(token) is None
        assert sqlite_repo.session_email(_hash_session_token(token)) == "testuser@example.com"

    def test_remove_session_invalidates_token(self, db):
        token, _ = create_session("testuser@example.com")
        remove_session(token)
        assert _validate_session_token(token) is None

    def test_expired_session_is_invalid_and_pruned(self, db):
        from db import sqlite_repo

        sqlite_repo.session_create(
            _hash_session_token("expired_token"),
            "testuser@example.com",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert _validate_session_token("expired_token") is None
        prune_expired_sessions()
        assert sqlite_repo.session_email(_hash_session_token("expired_token")) is None

    def test_prune_keeps_valid_sessions(self, db):
        token, _ = create_session("testuser@example.com")
        prune_expired_sessions()
        assert _validate_session_token(token) == "testuser@example.com"


class TestCredentialVerification:
    """Test credential verification."""

    def test_hash_secret_roundtrip(self):
        """A hashed secret should verify against its plaintext."""
        from auth import hash_secret, verify_secret

        stored = hash_secret("correct-horse-battery-staple")
        assert verify_secret("correct-horse-battery-staple", stored)
        assert not verify_secret("wrong-password", stored)
        assert not verify_secret("correct-horse-battery-staple", None)

    def test_secret_verification_is_timing_safe(self):
        """verify_secret must use hmac.compare_digest under the hood."""
        import inspect
        from auth import verify_secret

        source = inspect.getsource(verify_secret)
        assert "compare_digest" in source


class TestUserEnumerationTiming:
    """Unknown-email logins must spend the same PBKDF2 time as known-user failures."""

    def test_unknown_user_verifies_against_real_dummy_hash(self, db, monkeypatch):
        import users
        from db import sqlite_repo

        captured = {}
        real_verify = sqlite_repo.verify_secret

        def spy(secret, stored):
            captured["stored"] = stored
            return real_verify(secret, stored)

        monkeypatch.setattr(sqlite_repo, "verify_secret", spy)
        # No user exists, so this is the unknown-email path; it must still run a
        # real PBKDF2 against the dummy hash (not short-circuit on None).
        assert users.authenticate_user("ghost@example.com", "some-long-password") is None
        assert captured["stored"] == users._DUMMY_PASSWORD_HASH

    def test_dummy_hash_is_a_real_pbkdf2_hash(self):
        from auth import verify_secret
        from users import _DUMMY_PASSWORD_HASH

        # A valid stored hash that no real password should match by accident.
        assert _DUMMY_PASSWORD_HASH.startswith("$pbkdf2_sha256$")
        assert not verify_secret("some-long-password", _DUMMY_PASSWORD_HASH)


def test_auth_cookie_secure_tracks_require_https(monkeypatch):
    """The session cookie's Secure flag follows APP_REQUIRE_HTTPS so it isn't dropped in HTTP dev."""
    from auth import auth_cookie_secure

    monkeypatch.setenv("APP_REQUIRE_HTTPS", "true")
    assert auth_cookie_secure() is True
    monkeypatch.setenv("APP_REQUIRE_HTTPS", "false")
    assert auth_cookie_secure() is False
    monkeypatch.delenv("APP_REQUIRE_HTTPS", raising=False)
    assert auth_cookie_secure() is False


