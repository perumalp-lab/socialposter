"""Tests for the Facebook platform plugin."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from socialposter.core.content import (
    DefaultContent,
    FacebookOverride,
    PlatformOverrides,
    PostFile,
)
from socialposter.platforms.facebook import FacebookPlatform


@pytest.fixture
def platform():
    return FacebookPlatform()


# ===================================================================
# validate()
# ===================================================================

class TestFacebookValidate:

    def test_missing_page_id_fails(self, platform):
        content = PostFile(
            defaults=DefaultContent(text="Hello Facebook"),
            platforms=PlatformOverrides(
                facebook=FacebookOverride(enabled=True, page_id=None),
            ),
        )
        with patch.object(platform, "_get_connection", return_value=None):
            errors = platform.validate(content, user_id=0)
        assert any("page_id" in e.lower() for e in errors)

    def test_empty_text_fails(self, platform):
        content = PostFile(
            defaults=DefaultContent(text=""),
            platforms=PlatformOverrides(
                facebook=FacebookOverride(enabled=True, page_id="123"),
            ),
        )
        errors = platform.validate(content, user_id=0)
        assert any("empty" in e.lower() for e in errors)

    def test_valid_text_with_page_id_passes(self, platform):
        content = PostFile(
            defaults=DefaultContent(text="Hello Facebook"),
            platforms=PlatformOverrides(
                facebook=FacebookOverride(enabled=True, page_id="123"),
            ),
        )
        errors = platform.validate(content, user_id=0)
        assert not errors


# ===================================================================
# authenticate()
# ===================================================================

class TestFacebookAuthenticate:

    def test_no_connection_returns_false(self, platform):
        with patch.object(platform, "_get_connection", return_value=None):
            assert platform.authenticate(user_id=0) is False

    def test_valid_connection(self, platform):
        mock_conn = MagicMock()
        mock_conn.access_token = "fake-page-token"

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(platform, "_get_connection", return_value=mock_conn), \
             patch("socialposter.platforms.facebook.requests.get", return_value=mock_resp):
            assert platform.authenticate(user_id=1) is True
