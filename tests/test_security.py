"""Tests for token encryption and CSRF protection."""

from __future__ import annotations

import os
import re
from unittest.mock import patch

import pytest


# ===================================================================
# Token encryption
# ===================================================================

class TestTokenEncryption:
    """Verify encrypt/decrypt round-trip and fallback behaviour."""

    def _reset_crypto_cache(self):
        """Reset the module-level cache so each test can set its own key."""
        import socialposter.utils.crypto as mod
        mod._fernet = None
        mod._checked = False

    def test_roundtrip_with_key(self):
        """Encrypt then decrypt should return the original plaintext."""
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()

        self._reset_crypto_cache()
        with patch.dict(os.environ, {"SOCIALPOSTER_ENCRYPTION_KEY": key}):
            from socialposter.utils.crypto import encrypt_token, decrypt_token
            self._reset_crypto_cache()
            ct = encrypt_token("my-secret-token")
            assert ct != "my-secret-token"  # actually encrypted
            assert decrypt_token(ct) == "my-secret-token"

    def test_plaintext_fallback_on_decrypt_failure(self):
        """If decrypt fails (token was stored as plaintext), return the original."""
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()

        self._reset_crypto_cache()
        with patch.dict(os.environ, {"SOCIALPOSTER_ENCRYPTION_KEY": key}):
            from socialposter.utils.crypto import decrypt_token
            self._reset_crypto_cache()
            # This is not valid Fernet ciphertext
            assert decrypt_token("plain-text-token") == "plain-text-token"

    def test_passthrough_when_no_key(self):
        """With no encryption key, tokens pass through unchanged."""
        self._reset_crypto_cache()
        with patch.dict(os.environ, {"SOCIALPOSTER_ENCRYPTION_KEY": ""}, clear=False):
            from socialposter.utils.crypto import encrypt_token, decrypt_token
            self._reset_crypto_cache()
            assert encrypt_token("hello") == "hello"
            assert decrypt_token("hello") == "hello"


# ===================================================================
# CSRF
# ===================================================================

class TestCSRFProtection:
    """Verify that CSRF is enforced on form-based endpoints."""

    @pytest.fixture
    def csrf_app(self):
        """Create a standalone app with CSRF enabled."""
        from socialposter.web.app import create_app
        from socialposter.web.models import db as _db

        app = create_app(test_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": True,
            "SECRET_KEY": "test-csrf-key",
        })
        with app.app_context():
            _db.drop_all()
            _db.create_all()
        return app

    def test_session_login_works_without_csrf(self, csrf_app):
        """The SPA's JSON auth endpoint must accept POST without a CSRF
        token (token_bp is intentionally CSRF-exempt). It should reject the
        request on auth grounds (401), not CSRF grounds (400)."""
        with csrf_app.test_client() as c:
            resp = c.post(
                "/api/auth/session-login",
                json={"email": "a@b.com", "password": "test1234"},
            )
            # 401 = auth failure (expected for unknown user); 400 would mean
            # CSRF rejected the request, which would break the SPA.
            assert resp.status_code == 401
