"""Tests for per-platform webhook payload handlers.

These tests exercise the in-process dispatch functions directly, asserting that
inbound payloads land as `InboxComment` rows for comment events and as
`Conversation` + `Message` rows for DM events.
"""

from __future__ import annotations

import pytest

from socialposter.web.webhook_handlers import dispatch
from socialposter.web.models import (
    Conversation,
    InboxComment,
    Message,
)


# ── Facebook / Instagram comment events ──


def test_facebook_feed_comment_creates_inbox_row(db):
    payload = {
        "object": "page",
        "entry": [{
            "id": "PAGE_42",
            "time": 1714600000,
            "changes": [{
                "field": "feed",
                "value": {
                    "item": "comment",
                    "verb": "add",
                    "comment_id": "PAGE_42_C1",
                    "post_id": "PAGE_42_P1",
                    "from": {"id": "U_1", "name": "Alice"},
                    "message": "Nice post",
                    "created_time": 1714600000,
                },
            }],
        }],
    }
    summary = dispatch("facebook", payload)
    assert summary == {"handled": True, "stored": 1}

    rows = InboxComment.query.filter_by(platform="facebook").all()
    assert len(rows) == 1
    row = rows[0]
    assert row.platform_comment_id == "PAGE_42_C1"
    assert row.platform_post_id == "PAGE_42_P1"
    assert row.author_name == "Alice"
    assert row.text == "Nice post"
    assert row.is_read is False


def test_facebook_replay_is_idempotent(db):
    payload = {
        "object": "page",
        "entry": [{
            "changes": [{
                "field": "feed",
                "value": {
                    "item": "comment",
                    "verb": "add",
                    "comment_id": "PAGE_42_C2",
                    "post_id": "PAGE_42_P2",
                    "from": {"name": "Bob"},
                    "message": "First",
                    "created_time": 1714600100,
                },
            }],
        }],
    }
    dispatch("facebook", payload)
    payload["entry"][0]["changes"][0]["value"]["message"] = "Replay"
    dispatch("facebook", payload)

    rows = InboxComment.query.filter_by(platform_comment_id="PAGE_42_C2").all()
    assert len(rows) == 1
    # Replay must NOT overwrite the original message text.
    assert rows[0].text == "First"


def test_facebook_ignores_non_comment_items(db):
    """A 'like' verb should be a no-op — no row created for that post."""
    before = InboxComment.query.filter_by(platform_post_id="PAGE_42_P3").count()
    payload = {
        "object": "page",
        "entry": [{
            "changes": [{
                "field": "feed",
                "value": {
                    "item": "like",  # not a comment
                    "verb": "add",
                    "post_id": "PAGE_42_P3",
                },
            }],
        }],
    }
    summary = dispatch("facebook", payload)
    assert summary == {"handled": True, "stored": 0}
    after = InboxComment.query.filter_by(platform_post_id="PAGE_42_P3").count()
    assert after == before


def test_instagram_comment_event(db):
    payload = {
        "object": "instagram",
        "entry": [{
            "id": "IG_BIZ_1",
            "changes": [{
                "field": "comments",
                "value": {
                    "id": "IG_C7",
                    "text": "Beautiful!",
                    "from": {"id": "IG_USER_1", "username": "fan_42"},
                    "media": {"id": "IG_MEDIA_3"},
                    "created_time": "2026-05-01T12:00:00+0000",
                },
            }],
        }],
    }
    summary = dispatch("instagram", payload)
    assert summary == {"handled": True, "stored": 1}

    row = InboxComment.query.filter_by(platform="instagram").one()
    assert row.platform_comment_id == "IG_C7"
    assert row.platform_post_id == "IG_MEDIA_3"
    assert row.author_name == "fan_42"
    assert row.text == "Beautiful!"


def test_meta_payload_with_object_instagram_routes_to_ig(db):
    """Webhook URL is /facebook but payload says object=instagram → IG handler."""
    payload = {
        "object": "instagram",
        "entry": [{
            "changes": [{
                "field": "comments",
                "value": {
                    "id": "IG_C8",
                    "text": "via meta route",
                    "from": {"username": "x"},
                    "media": {"id": "IG_M_1"},
                },
            }],
        }],
    }
    summary = dispatch("facebook", payload)  # platform=facebook, object=instagram
    assert summary == {"handled": True, "stored": 1}
    row = InboxComment.query.filter_by(
        platform="instagram", platform_comment_id="IG_C8",
    ).one()
    assert row.text == "via meta route"


# ── WhatsApp DM events ──


def test_whatsapp_text_message_creates_conversation_and_message(db):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_1",
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{
                        "wa_id": "+15551111111",
                        "profile": {"name": "Carol"},
                    }],
                    "messages": [{
                        "id": "wamid.A1",
                        "from": "+15551111111",
                        "timestamp": "1714600000",
                        "type": "text",
                        "text": {"body": "Hello there"},
                    }],
                },
            }],
        }],
    }
    summary = dispatch("whatsapp", payload)
    assert summary == {"handled": True, "stored": 1}

    conv = Conversation.query.filter_by(
        platform="whatsapp", platform_thread_id="+15551111111"
    ).one()
    assert conv.participant_name == "Carol"
    assert conv.unread_count == 1
    assert conv.last_message_text == "Hello there"

    msgs = Message.query.filter_by(conversation_id=conv.id).all()
    assert len(msgs) == 1
    assert msgs[0].direction == "in"
    assert msgs[0].sender_type == "customer"


def test_whatsapp_second_message_updates_rollup(db):
    """Two inbound messages should update last_message_* and increment unread."""
    base = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{
                        "wa_id": "+15552222222",
                        "profile": {"name": "Dan"},
                    }],
                    "messages": [],
                },
            }],
        }],
    }
    base["entry"][0]["changes"][0]["value"]["messages"] = [{
        "id": "wamid.B1",
        "from": "+15552222222",
        "timestamp": "1714600000",
        "type": "text",
        "text": {"body": "First"},
    }]
    dispatch("whatsapp", base)

    base["entry"][0]["changes"][0]["value"]["messages"] = [{
        "id": "wamid.B2",
        "from": "+15552222222",
        "timestamp": "1714600600",  # 10 minutes later
        "type": "text",
        "text": {"body": "Second — newer"},
    }]
    dispatch("whatsapp", base)

    conv = Conversation.query.filter_by(
        platform_thread_id="+15552222222"
    ).one()
    assert conv.unread_count == 2
    assert conv.last_message_text == "Second — newer"

    msgs = Message.query.filter_by(conversation_id=conv.id).all()
    assert len(msgs) == 2
    assert {m.platform_message_id for m in msgs} == {"wamid.B1", "wamid.B2"}


def test_whatsapp_image_caption_extracted(db):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{"wa_id": "+15553333333"}],
                    "messages": [{
                        "id": "wamid.IMG1",
                        "from": "+15553333333",
                        "timestamp": "1714600000",
                        "type": "image",
                        "image": {"caption": "look at this"},
                    }],
                },
            }],
        }],
    }
    dispatch("whatsapp", payload)
    msg = Message.query.filter_by(platform_message_id="wamid.IMG1").one()
    assert msg.text.startswith("[image]")
    assert "look at this" in msg.text


def test_whatsapp_replay_is_idempotent(db):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{"wa_id": "+15554444444"}],
                    "messages": [{
                        "id": "wamid.DUPE",
                        "from": "+15554444444",
                        "timestamp": "1714600000",
                        "type": "text",
                        "text": {"body": "once"},
                    }],
                },
            }],
        }],
    }
    dispatch("whatsapp", payload)
    dispatch("whatsapp", payload)

    msgs = Message.query.filter_by(platform_message_id="wamid.DUPE").all()
    assert len(msgs) == 1
    conv = Conversation.query.filter_by(
        platform_thread_id="+15554444444"
    ).one()
    assert conv.unread_count == 1  # not bumped twice


# ── Twitter DM events ──


def test_twitter_inbound_dm(db):
    """Sender != for_user_id → inbound, customer."""
    payload = {
        "for_user_id": "BIZ_1",
        "direct_message_events": [{
            "type": "message_create",
            "id": "DM_1",
            "created_timestamp": "1714600000000",
            "message_create": {
                "target": {"recipient_id": "BIZ_1"},
                "sender_id": "USER_X",
                "message_data": {"text": "hey"},
            },
        }],
        "users": {
            "BIZ_1": {"id": "BIZ_1", "name": "Brand", "screen_name": "brand"},
            "USER_X": {
                "id": "USER_X",
                "name": "Eve Customer",
                "screen_name": "eve_x",
            },
        },
    }
    summary = dispatch("twitter", payload)
    assert summary == {"handled": True, "stored": 1}

    conv = Conversation.query.filter_by(
        platform="twitter", platform_thread_id="USER_X"
    ).one()
    assert conv.participant_name == "Eve Customer"
    assert conv.unread_count == 1
    msg = Message.query.filter_by(conversation_id=conv.id).one()
    assert msg.direction == "in"
    assert msg.sender_type == "customer"
    assert msg.text == "hey"


def test_linkedin_comment_created_event(db):
    payload = {
        "eventType": "COMMENT_CREATED",
        "comment": {
            "id": "urn:li:comment:(activity:7000,9001)",
            "actor": "urn:li:person:eve_xyz",
            "object": "urn:li:activity:7000",
            "message": {"text": "Insightful read."},
            "createdAt": 1714600000000,
        },
    }
    summary = dispatch("linkedin", payload)
    assert summary == {"handled": True, "stored": 1}

    row = InboxComment.query.filter_by(
        platform="linkedin",
        platform_comment_id="urn:li:comment:(activity:7000,9001)",
    ).one()
    assert row.text == "Insightful read."
    assert row.platform_post_id == "urn:li:activity:7000"
    assert row.author_name == "eve_xyz"
    assert "linkedin.com" in row.author_profile_url


def test_linkedin_ignores_reaction_events(db):
    """LIKE_CREATED is not a comment — must be a no-op."""
    before = InboxComment.query.filter_by(platform="linkedin").count()
    payload = {
        "eventType": "LIKE_CREATED",
        "comment": {"id": "urn:li:reaction:abc"},
    }
    summary = dispatch("linkedin", payload)
    assert summary == {"handled": True, "stored": 0}
    after = InboxComment.query.filter_by(platform="linkedin").count()
    assert after == before


def test_youtube_atom_feed_counts_entries(db):
    """Atom feeds parsed by webhook_routes are passed through as a tag-tree dict."""
    # Mirrors what _atom_to_dict produces for a 1-entry YouTube feed.
    payload = {
        "tag": "feed",
        "children": [
            {"tag": "title", "text": "Channel feed"},
            {
                "tag": "entry",
                "children": [
                    {"tag": "id", "text": "yt:video:VID_1"},
                    {"tag": "videoId", "text": "VID_1"},
                    {"tag": "channelId", "text": "CHAN_1"},
                    {"tag": "title", "text": "New video"},
                ],
                "videoId": "VID_1",
                "channelId": "CHAN_1",
                "title": "New video",
            },
        ],
    }
    summary = dispatch("youtube", payload)
    assert summary == {"handled": True, "stored": 1}


def test_youtube_no_entries_is_zero(db):
    payload = {"tag": "feed", "children": [{"tag": "title", "text": "Empty"}]}
    summary = dispatch("youtube", payload)
    assert summary == {"handled": True, "stored": 0}


def test_youtube_non_feed_payload_is_ignored(db):
    """A payload missing tag=feed shouldn't crash — just returns 0."""
    summary = dispatch("youtube", {"unexpected": "shape"})
    assert summary == {"handled": True, "stored": 0}


def test_linkedin_replay_is_idempotent(db):
    payload = {
        "eventType": "COMMENT_CREATED",
        "comment": {
            "id": "urn:li:comment:(activity:8000,9002)",
            "actor": "urn:li:person:dup_test",
            "object": "urn:li:activity:8000",
            "message": {"text": "first"},
            "createdAt": 1714600100000,
        },
    }
    dispatch("linkedin", payload)
    payload["comment"]["message"]["text"] = "replay"
    dispatch("linkedin", payload)

    rows = InboxComment.query.filter_by(
        platform_comment_id="urn:li:comment:(activity:8000,9002)",
    ).all()
    assert len(rows) == 1
    assert rows[0].text == "first"  # original preserved


def test_twitter_outbound_dm_does_not_bump_unread(db):
    """Sender == for_user_id → outbound; thread is keyed on recipient_id."""
    payload = {
        "for_user_id": "BIZ_2",
        "direct_message_events": [{
            "type": "message_create",
            "id": "DM_OUT_1",
            "created_timestamp": "1714600000000",
            "message_create": {
                "target": {"recipient_id": "USER_Y"},
                "sender_id": "BIZ_2",
                "message_data": {"text": "hi customer"},
            },
        }],
        "users": {
            "BIZ_2": {"id": "BIZ_2", "name": "Brand2", "screen_name": "brand2"},
            "USER_Y": {"id": "USER_Y", "name": "Yvonne", "screen_name": "yv"},
        },
    }
    dispatch("twitter", payload)

    conv = Conversation.query.filter_by(
        platform="twitter", platform_thread_id="USER_Y"
    ).one()
    assert conv.unread_count == 0  # not bumped on outbound
    msg = Message.query.filter_by(conversation_id=conv.id).one()
    assert msg.direction == "out"
    assert msg.sender_type == "user"
