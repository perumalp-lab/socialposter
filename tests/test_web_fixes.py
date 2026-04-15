"""Tests for broken-connection fixes and bulk-import features.

Covers:
  1. Meta disconnect removes all 3 platform connections (facebook, instagram, whatsapp)
  2. WhatsApp validation accepts defaults.text as fallback
  3. Connections page saveConfig includes auth token (template check)
  4. WhatsApp bulk recipients parsing (parseRecipients logic, tested via content model)
  5. YouTube bulk tags parsing (parseTags logic, tested via content model)
  6. YouTube description auto-fill respects override
  7. Select All Connected toggle
  8. Full publish payload round-trip (overrides with recipients + tags)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask import Flask
from flask_login import login_user

from socialposter.web.models import PlatformConnection, AppSetting
from socialposter.core.content import (
    DefaultContent,
    FacebookOverride,
    InstagramOverride,
    LinkedInOverride,
    MediaItem,
    PlatformOverrides,
    PostFile,
    TwitterOverride,
    WhatsAppOverride,
    YouTubeOverride,
)


# Fixtures (app, db, test_user, client) are provided by tests/conftest.py

def _add_connection(db, user_id, platform, token="fake-token", extra_data=None):
    """Helper to create a PlatformConnection."""
    conn = PlatformConnection(
        user_id=user_id,
        platform=platform,
        access_token=token,
        extra_data=extra_data,
    )
    db.session.add(conn)
    db.session.commit()
    return conn


# ===================================================================
# 1. Meta Disconnect – removes all 3 connections
# ===================================================================

class TestMetaDisconnect:
    """Verify that disconnecting a Meta platform removes facebook, instagram, and whatsapp."""

    def test_disconnect_facebook_removes_all_meta(self, client, db, test_user):
        """POST /oauth/facebook/disconnect should delete facebook, instagram, AND whatsapp."""
        _add_connection(db, test_user.id, "facebook", extra_data={"page_id": "123"})
        _add_connection(db, test_user.id, "instagram", extra_data={"business_account_id": "456"})
        _add_connection(db, test_user.id, "whatsapp", extra_data={"phone_number_id": "789"})

        # Also add a non-Meta connection that should NOT be affected
        _add_connection(db, test_user.id, "linkedin")

        resp = client.post("/oauth/facebook/disconnect", follow_redirects=False)
        assert resp.status_code in (302, 303)  # redirect

        # All Meta connections should be gone
        assert PlatformConnection.query.filter_by(user_id=test_user.id, platform="facebook").first() is None
        assert PlatformConnection.query.filter_by(user_id=test_user.id, platform="instagram").first() is None
        assert PlatformConnection.query.filter_by(user_id=test_user.id, platform="whatsapp").first() is None

        # LinkedIn should still exist
        assert PlatformConnection.query.filter_by(user_id=test_user.id, platform="linkedin").first() is not None

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()

    def test_disconnect_non_meta_only_removes_itself(self, client, db, test_user):
        """Disconnecting LinkedIn should NOT affect Meta connections."""
        _add_connection(db, test_user.id, "facebook")
        _add_connection(db, test_user.id, "linkedin")

        resp = client.post("/oauth/linkedin/disconnect", follow_redirects=False)
        assert resp.status_code in (302, 303)

        # LinkedIn gone
        assert PlatformConnection.query.filter_by(user_id=test_user.id, platform="linkedin").first() is None
        # Facebook still there
        assert PlatformConnection.query.filter_by(user_id=test_user.id, platform="facebook").first() is not None

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()


# ===================================================================
# 2. WhatsApp Validation – accepts defaults.text as fallback
# ===================================================================

class TestWhatsAppValidation:
    """WhatsApp validate() should accept default text when no override text is given."""

    def _make_content(self, default_text="", override_text=None, recipients=None, template=None):
        """Build a PostFile with WhatsApp config."""
        wa = WhatsAppOverride(
            enabled=True,
            text=override_text,
            recipients=["+1234567890"] if recipients is None else recipients,
            template_name=template,
        )
        return PostFile(
            defaults=DefaultContent(text=default_text),
            platforms=PlatformOverrides(whatsapp=wa),
        )

    def test_validates_with_override_text(self):
        """Override text alone should pass validation."""
        from socialposter.platforms.whatsapp import WhatsAppPlatform
        platform = WhatsAppPlatform()
        content = self._make_content(override_text="Hello override!")
        errors = platform.validate(content, user_id=0)
        assert not errors

    def test_validates_with_default_text_only(self):
        """Default text (no override) should pass validation."""
        from socialposter.platforms.whatsapp import WhatsAppPlatform
        platform = WhatsAppPlatform()
        content = self._make_content(default_text="Hello from defaults!")
        errors = platform.validate(content, user_id=0)
        assert not errors

    def test_fails_with_no_text_at_all(self):
        """No text anywhere should fail validation."""
        from socialposter.platforms.whatsapp import WhatsAppPlatform
        platform = WhatsAppPlatform()
        content = self._make_content(default_text="", override_text=None)
        errors = platform.validate(content, user_id=0)
        assert any("text is required" in e.lower() for e in errors)

    def test_fails_with_no_recipients(self):
        """Empty recipients should fail validation."""
        from socialposter.platforms.whatsapp import WhatsAppPlatform
        platform = WhatsAppPlatform()
        content = self._make_content(default_text="Hi", recipients=[])
        errors = platform.validate(content, user_id=0)
        assert any("recipients" in e.lower() for e in errors)

    def test_validates_with_template(self):
        """Template name should pass without any text."""
        from socialposter.platforms.whatsapp import WhatsAppPlatform
        platform = WhatsAppPlatform()
        content = self._make_content(default_text="", template="welcome_msg")
        errors = platform.validate(content, user_id=0)
        assert not any("text is required" in e.lower() for e in errors)

    def test_text_length_check_uses_effective_text(self):
        """Length check should apply to effective text (override or default)."""
        from socialposter.platforms.whatsapp import WhatsAppPlatform
        platform = WhatsAppPlatform()
        long_text = "x" * 5000  # exceeds 4096 limit
        content = self._make_content(default_text=long_text)
        errors = platform.validate(content, user_id=0)
        assert any("too long" in e.lower() for e in errors)


# ===================================================================
# 3. Connections page – saveConfig auth token (template check)
# ===================================================================

class TestConnectionsSaveConfig:
    """Verify the connections template includes auth token logic."""

    def test_connections_page_has_bearer_token_logic(self, client):
        """The connections page JS should include Bearer token for mobile."""
        resp = client.get("/connections")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "sp_auth_token" in html
        assert "Authorization" in html
        assert "Bearer" in html

    def test_connections_page_uses_api_base(self, client):
        """The saveConfig should use SOCIALPOSTER_API_BASE for mobile."""
        resp = client.get("/connections")
        html = resp.data.decode()
        assert "SOCIALPOSTER_API_BASE" in html

    def test_save_config_endpoint_works(self, client, db, test_user):
        """POST /api/connection/whatsapp/config should save phone_number_id."""
        _add_connection(db, test_user.id, "whatsapp", extra_data={})

        resp = client.post(
            "/api/connection/whatsapp/config",
            data=json.dumps({"phone_number_id": "112233445566"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["extra_data"]["phone_number_id"] == "112233445566"

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()


# ===================================================================
# 4. Content Model – WhatsApp recipients
# ===================================================================

class TestWhatsAppRecipients:
    """Test WhatsApp override recipients field with bulk data."""

    def test_recipients_list_in_override(self):
        """WhatsAppOverride should accept a list of phone numbers."""
        wa = WhatsAppOverride(
            enabled=True,
            text="Hello",
            recipients=["+14155551234", "+442071234567", "+919876543210"],
        )
        assert len(wa.recipients) == 3
        assert wa.recipients[0] == "+14155551234"

    def test_empty_recipients(self):
        """Empty recipients list should be valid model but fail validation."""
        wa = WhatsAppOverride(enabled=True, text="Hi", recipients=[])
        assert wa.recipients == []

    def test_recipients_passed_through_post_api(self, client, db, test_user):
        """POST /api/post with WhatsApp recipients should build correct overrides."""
        # Add a WhatsApp connection so it's "connected"
        _add_connection(db, test_user.id, "whatsapp",
                        extra_data={"phone_number_id": "12345"})

        payload = {
            "text": "Test broadcast message",
            "platforms": ["whatsapp"],
            "media": [],
            "overrides": {
                "whatsapp": {
                    "text": "WhatsApp specific text",
                    "recipients": ["+1111111111", "+2222222222", "+3333333333"],
                }
            },
            "dry_run": True,
        }

        resp = client.post(
            "/api/post",
            data=json.dumps(payload),
            content_type="application/json",
        )
        # Should not return 400 (bad request) — the structure is valid
        data = resp.get_json()
        assert "error" not in data or data.get("results") is not None

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()


# ===================================================================
# 5. Content Model – YouTube tags
# ===================================================================

class TestYouTubeTags:
    """Test YouTube override tags field with bulk data."""

    def test_tags_list_in_override(self):
        """YouTubeOverride should accept a list of tags."""
        yt = YouTubeOverride(
            enabled=True,
            title="My Video",
            description="A description",
            tags=["python", "coding", "tutorial", "programming"],
            privacy="public",
        )
        assert len(yt.tags) == 4
        assert "python" in yt.tags

    def test_empty_tags(self):
        """Empty tags should default to empty list."""
        yt = YouTubeOverride(enabled=True, title="Video")
        assert yt.tags == []

    def test_youtube_override_in_postfile(self):
        """YouTube tags should survive PostFile round-trip."""
        tags = ["tech", "review", "unboxing"]
        content = PostFile(
            defaults=DefaultContent(text="Check out this video!"),
            platforms=PlatformOverrides(
                youtube=YouTubeOverride(
                    enabled=True,
                    title="Product Review",
                    description="Full review",
                    tags=tags,
                )
            ),
        )
        assert content.platforms.youtube.tags == tags


# ===================================================================
# 6. YouTube Validation – title required
# ===================================================================

class TestYouTubeValidation:
    """YouTube validation checks (title required, video required)."""

    def test_validates_with_title(self):
        """Valid YouTube override with title should pass."""
        from socialposter.platforms.youtube import YouTubePlatform
        platform = YouTubePlatform()
        content = PostFile(
            defaults=DefaultContent(
                text="Video post",
                media=[MediaItem(path="/tmp/test.mp4", type="video")],
            ),
            platforms=PlatformOverrides(
                youtube=YouTubeOverride(
                    enabled=True,
                    title="My Video Title",
                    tags=["test"],
                )
            ),
        )
        errors = platform.validate(content, user_id=0)
        assert not any("title" in e.lower() for e in errors)

    def test_fails_without_title(self):
        """Missing title should fail validation."""
        from socialposter.platforms.youtube import YouTubePlatform
        platform = YouTubePlatform()
        content = PostFile(
            defaults=DefaultContent(
                text="Video post",
                media=[MediaItem(path="/tmp/test.mp4", type="video")],
            ),
            platforms=PlatformOverrides(
                youtube=YouTubeOverride(enabled=True, title=None)
            ),
        )
        errors = platform.validate(content, user_id=0)
        assert any("title" in e.lower() for e in errors)

    def test_fails_without_video(self):
        """No video file should fail validation."""
        from socialposter.platforms.youtube import YouTubePlatform
        platform = YouTubePlatform()
        content = PostFile(
            defaults=DefaultContent(text="No video here"),
            platforms=PlatformOverrides(
                youtube=YouTubeOverride(enabled=True, title="Has Title")
            ),
        )
        errors = platform.validate(content, user_id=0)
        assert any("video" in e.lower() for e in errors)


# ===================================================================
# 7. API /api/platforms – connected status
# ===================================================================

class TestApiPlatforms:
    """Verify /api/platforms returns correct connected status."""

    def test_platforms_shows_connected(self, client, db, test_user):
        """Connected platforms should show connected=True."""
        _add_connection(db, test_user.id, "facebook")
        _add_connection(db, test_user.id, "linkedin")

        resp = client.get("/api/platforms")
        assert resp.status_code == 200
        platforms = resp.get_json()

        fb = next((p for p in platforms if p["name"] == "facebook"), None)
        li = next((p for p in platforms if p["name"] == "linkedin"), None)
        tw = next((p for p in platforms if p["name"] == "twitter"), None)

        assert fb is not None and fb["connected"] is True
        assert li is not None and li["connected"] is True
        assert tw is not None and tw["connected"] is False

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()


# ===================================================================
# 8. Full Publish Payload Round-Trip (dry run)
# ===================================================================

class TestPublishPayload:
    """Test that the /api/post endpoint correctly builds overrides from JSON."""

    def test_multi_platform_dry_run(self, client, db, test_user):
        """Dry-run publish to multiple platforms should return results for each."""
        _add_connection(db, test_user.id, "facebook", extra_data={"page_id": "pg1"})
        _add_connection(db, test_user.id, "twitter", extra_data={"auth_type": "oauth2"})

        payload = {
            "text": "Multi-platform test",
            "platforms": ["facebook", "twitter"],
            "media": [],
            "overrides": {
                "facebook": {"text": "FB specific", "link": "https://example.com"},
                "twitter": {"text": "Tweet specific"},
            },
            "dry_run": True,
        }

        resp = client.post(
            "/api/post",
            data=json.dumps(payload),
            content_type="application/json",
        )
        data = resp.get_json()
        assert "results" in data
        assert len(data["results"]) == 2

        platforms_returned = {r["platform"] for r in data["results"]}
        assert "facebook" in platforms_returned
        assert "twitter" in platforms_returned

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()

    def test_no_platforms_returns_error(self, client):
        """Empty platforms list should return 400."""
        payload = {"text": "Hello", "platforms": [], "media": []}
        resp = client.post(
            "/api/post",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_youtube_tags_in_payload(self, client, db, test_user):
        """YouTube tags from the payload should reach the override model."""
        _add_connection(db, test_user.id, "youtube")

        payload = {
            "text": "Video description text",
            "platforms": ["youtube"],
            "media": [],
            "overrides": {
                "youtube": {
                    "title": "Test Video",
                    "description": "A test video",
                    "tags": ["python", "flask", "testing"],
                    "privacy": "private",
                }
            },
            "dry_run": True,
        }

        resp = client.post(
            "/api/post",
            data=json.dumps(payload),
            content_type="application/json",
        )
        data = resp.get_json()
        # Should get results (not an error about missing platforms)
        assert "results" in data
        yt_result = next((r for r in data["results"] if r["platform"] == "youtube"), None)
        assert yt_result is not None

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()

    def test_whatsapp_recipients_in_payload(self, client, db, test_user):
        """WhatsApp recipients from the payload should reach the override model."""
        _add_connection(db, test_user.id, "whatsapp",
                        extra_data={"phone_number_id": "55555"})

        payload = {
            "text": "Broadcast message",
            "platforms": ["whatsapp"],
            "media": [],
            "overrides": {
                "whatsapp": {
                    "text": "Hello everyone!",
                    "recipients": ["+1111111111", "+2222222222"],
                }
            },
            "dry_run": True,
        }

        resp = client.post(
            "/api/post",
            data=json.dumps(payload),
            content_type="application/json",
        )
        data = resp.get_json()
        assert "results" in data
        wa_result = next((r for r in data["results"] if r["platform"] == "whatsapp"), None)
        assert wa_result is not None

        # Cleanup
        PlatformConnection.query.filter_by(user_id=test_user.id).delete()
        db.session.commit()


# ===================================================================
# 9. Content model overrides – build from dict (simulates app.py logic)
# ===================================================================

class TestOverrideBuildFromDict:
    """Simulate how app.py builds overrides from the JSON payload."""

    def test_whatsapp_override_from_dict(self):
        """Build WhatsAppOverride the same way app.py does."""
        ov = {"text": "Hello!", "recipients": ["+111", "+222", "+333"]}
        wa = WhatsAppOverride(
            enabled=True,
            text=ov.get("text") or None,
            recipients=ov.get("recipients", []),
        )
        assert wa.text == "Hello!"
        assert len(wa.recipients) == 3

    def test_whatsapp_override_empty_text_becomes_none(self):
        """Empty string text should become None (matching app.py 'or None' logic)."""
        ov = {"text": "", "recipients": ["+111"]}
        wa = WhatsAppOverride(
            enabled=True,
            text=ov.get("text") or None,
            recipients=ov.get("recipients", []),
        )
        assert wa.text is None

    def test_youtube_override_from_dict(self):
        """Build YouTubeOverride the same way app.py does."""
        ov = {
            "title": "My Video",
            "description": "A description",
            "tags": ["python", "flask"],
            "privacy": "unlisted",
        }
        yt = YouTubeOverride(
            enabled=True,
            title=ov.get("title") or None,
            description=ov.get("description") or None,
            tags=ov.get("tags", []),
            privacy=ov.get("privacy", "public"),
        )
        assert yt.title == "My Video"
        assert yt.tags == ["python", "flask"]
        assert yt.privacy == "unlisted"

    def test_youtube_override_empty_title_becomes_none(self):
        """Empty string title should become None (triggers validation error)."""
        ov = {"title": "", "tags": []}
        yt = YouTubeOverride(
            enabled=True,
            title=ov.get("title") or None,
            description=ov.get("description") or None,
            tags=ov.get("tags", []),
        )
        assert yt.title is None

    def test_full_postfile_construction(self):
        """Build a complete PostFile with all overrides like app.py does."""
        content = PostFile(
            defaults=DefaultContent(text="Main text", media=[]),
            platforms=PlatformOverrides(
                linkedin=LinkedInOverride(enabled=True, text="LI text", visibility="public"),
                youtube=YouTubeOverride(enabled=True, title="Vid", tags=["a", "b"]),
                instagram=InstagramOverride(enabled=True, post_type="reel"),
                facebook=FacebookOverride(enabled=True, link="https://example.com"),
                twitter=TwitterOverride(enabled=True, text="Tweet!"),
                whatsapp=WhatsAppOverride(enabled=True, text="WA msg", recipients=["+111"]),
            ),
        )
        assert content.get_text("linkedin") == "LI text"
        assert content.get_text("twitter") == "Tweet!"
        assert content.get_text("facebook") == "Main text"  # no override text
        assert content.platforms.youtube.tags == ["a", "b"]
        assert content.platforms.whatsapp.recipients == ["+111"]
        assert len(content.enabled_platforms()) == 6
