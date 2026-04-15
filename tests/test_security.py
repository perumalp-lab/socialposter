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

    def test_login_post_without_csrf_rejected(self, csrf_app):
        """POST to /login without a CSRF token should be rejected."""
        with csrf_app.test_client() as c:
            resp = c.post("/login", data={"email": "a@b.com", "password": "test1234"})
            assert resp.status_code == 400  # CSRF validation failure

    def test_login_post_with_csrf_accepted(self, csrf_app):
        """POST to /login with a valid CSRF token should not get a 400 CSRF error."""
        with csrf_app.test_client() as c:
            # GET the login page to obtain the CSRF token
            get_resp = c.get("/login")
            html = get_resp.data.decode()
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
            assert match, "CSRF token not found in login page"
            token = match.group(1)

            resp = c.post("/login", data={
                "email": "a@b.com",
                "password": "test1234",
                "csrf_token": token,
            })
            # Should NOT be 400 (CSRF); will be a redirect or re-render
            assert resp.status_code != 400
