"""Integration tests for the inbox conversation/message API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


def _team_id_for(user_id: int) -> int | None:
    from socialposter.utils.team import get_current_team_id
    return get_current_team_id(user_id)


def _make_conversation(
    db, user_id, *, platform="whatsapp", thread_id="+15558880001",
    name="Tester", unread_count=0, last_text="", last_at=None,
):
    from socialposter.web.models import Conversation
    conv = Conversation(
        team_id=_team_id_for(user_id),
        platform=platform,
        platform_thread_id=thread_id,
        participant_id=thread_id,
        participant_name=name,
        unread_count=unread_count,
        last_message_text=last_text,
        last_message_at=last_at,
    )
    db.session.add(conv)
    db.session.commit()
    return conv


def _add_message(db, conv, *, text, direction="in", message_id="m_1", sent_at=None):
    from socialposter.web.models import Message
    msg = Message(
        conversation_id=conv.id,
        platform_message_id=message_id,
        direction=direction,
        sender_type="customer" if direction == "in" else "user",
        sender_name="Tester" if direction == "in" else "Bot",
        text=text,
        sent_at=sent_at or datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(msg)
    db.session.commit()
    return msg


# ── GET /api/inbox/conversations ──


def test_conversations_list_returns_team_threads(client, db, test_user):
    conv = _make_conversation(
        db, test_user.id,
        thread_id="+15559990001", name="Alice",
        unread_count=2, last_text="latest", last_at=datetime(2026, 5, 1, 12, 0),
    )
    try:
        resp = client.get("/api/inbox/conversations")
        assert resp.status_code == 200
        body = resp.get_json()
        ids = [item["id"] for item in body["items"]]
        assert conv.id in ids

        item = next(x for x in body["items"] if x["id"] == conv.id)
        assert item["platform"] == "whatsapp"
        assert item["participant_name"] == "Alice"
        assert item["unread_count"] == 2
        assert item["last_message_text"] == "latest"
    finally:
        from socialposter.web.models import Conversation
        Conversation.query.filter_by(id=conv.id).delete()
        db.session.commit()


# ── GET /api/inbox/conversations/<id>/messages ──


def test_conversation_messages_zeros_unread_on_read(client, db, test_user):
    conv = _make_conversation(
        db, test_user.id,
        thread_id="+15559990002", name="Bob", unread_count=3,
    )
    _add_message(db, conv, text="Hi", message_id="zr_1")
    _add_message(db, conv, text="Hello", message_id="zr_2")
    try:
        resp = client.get(f"/api/inbox/conversations/{conv.id}/messages")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["conversation"]["id"] == conv.id
        texts = [m["text"] for m in body["items"]]
        assert "Hi" in texts and "Hello" in texts

        # Endpoint zeroes unread_count after reading.
        from socialposter.web.models import Conversation
        refreshed = Conversation.query.get(conv.id)
        assert refreshed.unread_count == 0
    finally:
        from socialposter.web.models import Conversation, Message
        Message.query.filter_by(conversation_id=conv.id).delete()
        Conversation.query.filter_by(id=conv.id).delete()
        db.session.commit()


def test_conversation_messages_returns_chat_order(client, db, test_user):
    conv = _make_conversation(db, test_user.id, thread_id="+15559990003")
    _add_message(
        db, conv, text="newer", message_id="co_2",
        sent_at=datetime(2026, 5, 1, 14, 0),
    )
    _add_message(
        db, conv, text="older", message_id="co_1",
        sent_at=datetime(2026, 5, 1, 13, 0),
    )
    try:
        resp = client.get(f"/api/inbox/conversations/{conv.id}/messages")
        body = resp.get_json()
        texts = [m["text"] for m in body["items"]]
        assert texts == ["older", "newer"]  # ascending by sent_at
    finally:
        from socialposter.web.models import Conversation, Message
        Message.query.filter_by(conversation_id=conv.id).delete()
        Conversation.query.filter_by(id=conv.id).delete()
        db.session.commit()


# ── GET /api/inbox/stats ──


def test_stats_includes_unread_message_counts(client, db, test_user):
    a = _make_conversation(
        db, test_user.id, thread_id="+15559990004",
        platform="whatsapp", unread_count=2,
    )
    b = _make_conversation(
        db, test_user.id, thread_id="USER_TW_1",
        platform="twitter", unread_count=1,
    )
    try:
        resp = client.get("/api/inbox/stats")
        assert resp.status_code == 200
        body = resp.get_json()
        # Pre-existing keys
        assert "unread" in body
        # New keys we added
        assert "unread_messages" in body
        assert "total_unread_messages" in body
        assert body["unread_messages"].get("whatsapp", 0) >= 2
        assert body["unread_messages"].get("twitter", 0) >= 1
        assert body["total_unread_messages"] >= 3
    finally:
        from socialposter.web.models import Conversation
        for conv in (a, b):
            Conversation.query.filter_by(id=conv.id).delete()
        db.session.commit()


# ── POST /api/inbox/conversations/<id>/ai-suggest ──


def test_ai_suggest_400_when_no_inbound_message(client, db, test_user):
    """AI suggest needs at least one inbound message to reply to."""
    conv = _make_conversation(db, test_user.id, thread_id="+15559990005")
    _add_message(db, conv, text="we sent this", direction="out", message_id="o_1")
    try:
        resp = client.post(
            f"/api/inbox/conversations/{conv.id}/ai-suggest",
            json={"tone": "friendly"},
        )
        assert resp.status_code == 400
        assert "inbound" in (resp.get_json() or {}).get("error", "").lower()
    finally:
        from socialposter.web.models import Conversation, Message
        Message.query.filter_by(conversation_id=conv.id).delete()
        Conversation.query.filter_by(id=conv.id).delete()
        db.session.commit()


# ── POST /api/inbox/conversations/<id>/reply ──


def test_reply_unsupported_platform_returns_501(client, db, test_user):
    """Linkedin has no send_text_message — must 501, not crash."""
    conv = _make_conversation(
        db, test_user.id,
        platform="linkedin", thread_id="urn:li:person:abc",
    )
    try:
        resp = client.post(
            f"/api/inbox/conversations/{conv.id}/reply",
            json={"text": "hello"},
        )
        assert resp.status_code == 501
        body = resp.get_json() or {}
        assert "linkedin" in body.get("error", "").lower()
    finally:
        from socialposter.web.models import Conversation
        Conversation.query.filter_by(id=conv.id).delete()
        db.session.commit()


def test_reply_blank_text_returns_400(client, db, test_user):
    conv = _make_conversation(db, test_user.id, thread_id="+15559990006")
    try:
        resp = client.post(
            f"/api/inbox/conversations/{conv.id}/reply",
            json={"text": "   "},
        )
        assert resp.status_code == 400
    finally:
        from socialposter.web.models import Conversation
        Conversation.query.filter_by(id=conv.id).delete()
        db.session.commit()


def test_reply_to_unknown_conversation_returns_404(client):
    resp = client.post(
        "/api/inbox/conversations/9999999/reply",
        json={"text": "hi"},
    )
    assert resp.status_code == 404
