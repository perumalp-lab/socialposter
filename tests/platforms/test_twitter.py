"""Tests for the Twitter/X platform plugin."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from socialposter.core.content import (
    DefaultContent,
    PlatformOverrides,
    PostFile,
    TwitterOverride,
    MediaItem,
)
from socialposter.platforms.twitter import TwitterPlatform


@pytest.fixture
def platform():
    return TwitterPlatform()


# ===================================================================
# validate()
# ===================================================================

class TestTwitterValidate:

    def test_empty_text_fails(self, platform):
        content = PostFile(
            defaults=DefaultContent(text=""),
            platforms=PlatformOverrides(twitter=TwitterOverride(enabled=True)),
        )
        errors = platform.validate(content, user_id=0)
        assert any("empty" in e.lower() for e in errors)

    def test_text_too_long_fails(self, platform):
        long_text = "x" * 281
        content = PostFile(
            defaults=DefaultContent(text=long_text),
            platforms=PlatformOverrides(twitter=TwitterOverride(enabled=True)),
        )
        errors = platform.validate(content, user_id=0)
        assert any("too long" in e.lower() for e in errors)

    def test_valid_text_passes(self, platform):
        content = PostFile(
            defaults=DefaultContent(text="Hello Twitter!"),
            platforms=PlatformOverrides(twitter=TwitterOverride(enabled=True)),
        )
        errors = platform.validate(content, user_id=0)
        assert not errors

    def test_override_text_used(self, platform):
        content = PostFile(
            defaults=DefaultContent(text="x" * 300),  # too long for twitter
            platforms=PlatformOverrides(
                twitter=TwitterOverride(enabled=True, text="Short tweet"),
            ),
        )
        errors = platform.validate(content, user_id=0)
        assert not errors


# ===================================================================
# authenticate()
# ===================================================================

class TestTwitterAuthenticate:

    def test_no_connection_returns_false(self, platform):
        """Without a DB connection, authenticate should fail."""
        with patch.object(platform, "_get_connection", return_value=None):
            assert platform.authenticate(user_id=0) is False

    def test_valid_connection(self, platform):
        """With a valid connection, authenticate should succeed."""
        mock_conn = MagicMock()
        mock_conn.access_token = "fake-bearer-token"

        mock_client = MagicMock()
        mock_me = MagicMock()
        mock_me.data = {"id": "12345", "name": "TestUser"}
        mock_client.get_me.return_value = mock_me

        with patch.object(platform, "_get_connection", return_value=mock_conn), \
             patch("tweepy.Client", return_value=mock_client):
            assert platform.authenticate(user_id=1) is True


# ===================================================================
# publish()
# ===================================================================

class TestTwitterPublish:

    def test_publish_success(self, platform):
        content = PostFile(
            defaults=DefaultContent(text="Test tweet"),
            platforms=PlatformOverrides(twitter=TwitterOverride(enabled=True)),
        )
        mock_conn = MagicMock()
        mock_conn.access_token = "fake-token"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"id": "99999"}
        mock_client.create_tweet.return_value = mock_response

        with patch.object(platform, "_get_connection", return_value=mock_conn), \
             patch("tweepy.Client", return_value=mock_client):
            result = platform.publish(content, user_id=1)

        assert result.success is True
        assert result.post_id == "99999"
        assert "x.com" in result.post_url

    def test_publish_thread(self, platform):
        content = PostFile(
            defaults=DefaultContent(text="Thread start"),
            platforms=PlatformOverrides(
                twitter=TwitterOverride(enabled=True, thread=["Reply 1", "Reply 2"]),
            ),
        )
        mock_conn = MagicMock()
        mock_conn.access_token = "fake-token"

        call_count = 0

        def make_tweet(**kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.data = {"id": str(1000 + call_count)}
            return resp

        mock_client = MagicMock()
        mock_client.create_tweet.side_effect = make_tweet

        with patch.object(platform, "_get_connection", return_value=mock_conn), \
             patch("tweepy.Client", return_value=mock_client):
            result = platform.publish(content, user_id=1)

        assert result.success is True
        # 1 main tweet + 2 thread replies = 3 calls
        assert mock_client.create_tweet.call_count == 3
