"""Fernet-based token encryption for OAuth tokens stored in the DB."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("socialposter")

_fernet = None
_checked = False


def _get_fernet():
    """Lazily build and cache a Fernet instance from the env var."""
    global _fernet, _checked
    if _checked:
        return _fernet
    _checked = True
    key = os.environ.get("SOCIALPOSTER_ENCRYPTION_KEY", "")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        logger.warning("Invalid SOCIALPOSTER_ENCRYPTION_KEY – tokens will not be encrypted")
        _fernet = None
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns ciphertext, or the original if no key is configured."""
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a token string.

    Graceful fallback: if decryption fails (e.g. token was stored before
    encryption was enabled), return the original string unchanged.
    """
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Likely a plaintext token from before encryption was enabled
        return ciphertext
