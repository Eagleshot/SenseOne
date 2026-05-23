"""Tests for authentication."""

import time

from auth import (
    create_session,
    prune_expired_sessions,
    AUTH_SESSIONS,
    AUTH_TOKEN_TTL_SECONDS,
)


class TestSessionManagement:
    """Test session creation and management."""

    def test_create_session(self):
        """Test creating a new session."""
        AUTH_SESSIONS.clear()
        token, ttl = create_session("testuser")
        
        assert isinstance(token, str)
        assert len(token) > 20  # Should be reasonably long
        assert ttl == AUTH_TOKEN_TTL_SECONDS
        assert token in AUTH_SESSIONS
        assert AUTH_SESSIONS[token][0] == "testuser"

    def test_session_has_expiry(self):
        """Test that sessions have expiry time."""
        AUTH_SESSIONS.clear()
        token, _ = create_session("testuser")
        
        username, expires_at = AUTH_SESSIONS[token]
        assert expires_at > time.time()
        assert expires_at - time.time() <= AUTH_TOKEN_TTL_SECONDS + 1

    def test_prune_expired_sessions(self):
        """Test pruning expired sessions."""
        AUTH_SESSIONS.clear()
        
        # Create a session with very short TTL
        token = "expired_token"
        AUTH_SESSIONS[token] = ("testuser", time.time() - 1)
        
        prune_expired_sessions()
        assert token not in AUTH_SESSIONS

    def test_prune_keeps_valid_sessions(self):
        """Test that pruning doesn't remove valid sessions."""
        AUTH_SESSIONS.clear()
        token, _ = create_session("testuser")
        
        prune_expired_sessions()
        assert token in AUTH_SESSIONS


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


def test_session_storage_is_mutable():
    """Test that AUTH_SESSIONS can be modified for testing."""
    AUTH_SESSIONS["test_token"] = ("user", time.time() + 3600)
    assert "test_token" in AUTH_SESSIONS
    AUTH_SESSIONS.pop("test_token")
    assert "test_token" not in AUTH_SESSIONS


