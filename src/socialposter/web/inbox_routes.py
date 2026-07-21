"""Unified inbox blueprint – view/reply to comments across platforms."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from socialposter.utils.datetime import isoformat_or
from socialposter.utils.pagination import paginate_query
from socialposter.utils.team import get_current_team_id
from socialposter.web.models import (
    Conversation,
    InboxComment,
    Message,
    db,
)
from socialposter.web.permissions import team_required

inbox_bp = Blueprint("inbox", __name__)


# /inbox Jinja page removed — React SPA owns it.


@inbox_bp.route("/api/inbox/comments")
@login_required
def api_inbox_comments():
    page = request.args.get("page", 1, type=int)
    platform_filter = request.args.get("platform", "")
    is_read_filter = request.args.get("is_read", "")

    team_id = get_current_team_id(current_user.id)

    query = InboxComment.query
    if team_id:
        query = query.filter(InboxComment.team_id == team_id)
    else:
        query = query.filter(InboxComment.team_id == None)  # noqa: E711

    if platform_filter:
        query = query.filter(InboxComment.platform == platform_filter)
    if is_read_filter == "true":
        query = query.filter(InboxComment.is_read == True)  # noqa: E712
    elif is_read_filter == "false":
        query = query.filter(InboxComment.is_read == False)  # noqa: E712

    query = query.order_by(InboxComment.fetched_at.desc())

    def _serialize(c):
        return {
            "id": c.id,
            "platform": c.platform,
            "author_name": c.author_name,
            "author_avatar_url": c.author_avatar_url,
            "text": c.text,
            "is_read": c.is_read,
            "platform_post_url": c.platform_post_url,
            "posted_at": isoformat_or(c.posted_at),
            "fetched_at": isoformat_or(c.fetched_at),
        }

    return jsonify(paginate_query(query, page, serializer=_serialize))


@inbox_bp.route("/api/inbox/comments/<int:comment_id>/read", methods=["POST"])
@login_required
def mark_read(comment_id: int):
    c = InboxComment.query.get_or_404(comment_id)
    c.is_read = True
    db.session.commit()
    return jsonify({"ok": True})


@inbox_bp.route("/api/inbox/comments/mark-read", methods=["POST"])
@login_required
def bulk_mark_read():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if ids:
        InboxComment.query.filter(InboxComment.id.in_(ids)).update(
            {"is_read": True}, synchronize_session=False
        )
    else:
        # Mark all
        team_id = get_current_team_id(current_user.id)
        q = InboxComment.query
        if team_id:
            q = q.filter(InboxComment.team_id == team_id)
        q.update({"is_read": True}, synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True})


@inbox_bp.route("/api/inbox/comments/<int:comment_id>/reply", methods=["POST"])
@login_required
def reply_to_comment(comment_id: int):
    c = InboxComment.query.get_or_404(comment_id)
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Reply text is required"}), 400

    from socialposter.platforms.registry import PlatformRegistry

    registry = PlatformRegistry.all()
    platform_cls = registry.get(c.platform)
    if not platform_cls:
        return jsonify({"error": f"Platform {c.platform} not found"}), 400

    platform_instance = platform_cls()
    if not platform_instance.supports_comment_fetching():
        return jsonify({"error": f"{c.platform} does not support replies"}), 400

    # Find the user ID that owns the connection
    from socialposter.web.models import PublishedPost
    pp = PublishedPost.query.filter_by(
        platform=c.platform, platform_post_id=c.platform_post_id
    ).first()
    user_id = pp.user_id if pp else current_user.id

    result = platform_instance.reply_to_comment(
        user_id=user_id,
        comment_id=c.platform_comment_id,
        post_id=c.platform_post_id,
        text=text,
    )
    if result.get("success"):
        c.is_read = True
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": result.get("error", "Reply failed")}), 500


@inbox_bp.route("/api/inbox/comments/<int:comment_id>/ai-suggest", methods=["POST"])
@login_required
def ai_suggest_reply(comment_id: int):
    """Draft an AI-generated reply for a comment without sending it."""
    import logging
    log = logging.getLogger("socialposter")

    c = InboxComment.query.get_or_404(comment_id)
    data = request.get_json(silent=True) or {}
    tone = (data.get("tone") or "friendly").strip() or "friendly"
    provider_name = (data.get("provider") or "").strip() or None
    model_id = (data.get("model") or "").strip() or None
    temperature = data.get("temperature")
    if temperature is not None:
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            temperature = None

    # Pull the original post text if available, for context.
    from socialposter.web.models import PublishedPost
    pp = PublishedPost.query.filter_by(
        platform=c.platform, platform_post_id=c.platform_post_id
    ).first()
    post_text = pp.text_preview if pp else ""

    try:
        from socialposter.core.ai_service import suggest_reply
        text = suggest_reply(
            comment_text=c.text,
            author_name=c.author_name or "",
            platform=c.platform,
            post_text=post_text,
            tone=tone,
            provider_name=provider_name,
            model_id=model_id,
            temperature=temperature,
            user_id=current_user.id,
        )
        return jsonify({"text": text})
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        log.exception("AI reply suggestion failed")
        return jsonify({"error": f"AI request failed: {e}"}), 502


@inbox_bp.route("/api/inbox/conversations")
@login_required
def api_conversations():
    """List DM conversations for the current team, newest activity first."""
    page = request.args.get("page", 1, type=int)
    platform_filter = request.args.get("platform", "")

    team_id = get_current_team_id(current_user.id)

    query = Conversation.query
    if team_id:
        query = query.filter(Conversation.team_id == team_id)
    else:
        query = query.filter(Conversation.team_id == None)  # noqa: E711
    if platform_filter:
        query = query.filter(Conversation.platform == platform_filter)
    query = query.order_by(
        Conversation.last_message_at.desc().nullslast(),
        Conversation.created_at.desc(),
    )

    def _serialize(c):
        return {
            "id": c.id,
            "platform": c.platform,
            "platform_thread_id": c.platform_thread_id,
            "participant_id": c.participant_id,
            "participant_name": c.participant_name,
            "participant_avatar_url": c.participant_avatar_url,
            "last_message_text": c.last_message_text,
            "last_message_at": isoformat_or(c.last_message_at),
            "unread_count": c.unread_count,
            "created_at": isoformat_or(c.created_at),
        }

    return jsonify(paginate_query(query, page, serializer=_serialize))


@inbox_bp.route("/api/inbox/conversations/<int:conversation_id>/messages")
@login_required
def api_conversation_messages(conversation_id: int):
    """List messages within a conversation, oldest first (chat order)."""
    team_id = get_current_team_id(current_user.id)
    conv = Conversation.query.filter_by(id=conversation_id).first_or_404()
    if team_id and conv.team_id and conv.team_id != team_id:
        return jsonify({"error": "Conversation not in current team"}), 403

    rows = (
        Message.query.filter_by(conversation_id=conv.id)
        .order_by(Message.sent_at.asc(), Message.id.asc())
        .all()
    )
    items = [
        {
            "id": m.id,
            "platform_message_id": m.platform_message_id,
            "direction": m.direction,
            "sender_type": m.sender_type,
            "sender_name": m.sender_name,
            "text": m.text,
            "sent_at": isoformat_or(m.sent_at),
        }
        for m in rows
    ]

    # Mark all unread inbound messages as "seen" by zeroing the conversation
    # counter — we do not need a per-message seen flag yet.
    if conv.unread_count:
        conv.unread_count = 0
        db.session.commit()

    return jsonify({
        "conversation": {
            "id": conv.id,
            "platform": conv.platform,
            "participant_name": conv.participant_name,
            "participant_avatar_url": conv.participant_avatar_url,
            "platform_thread_id": conv.platform_thread_id,
        },
        "items": items,
    })


@inbox_bp.route(
    "/api/inbox/conversations/<int:conversation_id>/reply", methods=["POST"]
)
@login_required
def api_conversation_reply(conversation_id: int):
    """Send a reply on this conversation's platform; record an outbound Message."""
    from datetime import datetime, timezone
    from socialposter.platforms.registry import PlatformRegistry

    team_id = get_current_team_id(current_user.id)
    conv = Conversation.query.filter_by(id=conversation_id).first_or_404()
    if team_id and conv.team_id and conv.team_id != team_id:
        return jsonify({"error": "Conversation not in current team"}), 403

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    platform_cls = PlatformRegistry.all().get(conv.platform)
    if platform_cls is None:
        return jsonify({"error": f"platform {conv.platform} not registered"}), 400

    instance = platform_cls()
    if not hasattr(instance, "send_text_message"):
        return jsonify({
            "error": f"Outbound replies on {conv.platform} are not implemented yet",
        }), 501

    message_id, error = instance.send_text_message(
        user_id=current_user.id,
        recipient=conv.platform_thread_id,
        text=text,
    )
    if error:
        return jsonify({"error": f"send failed: {error}"}), 502

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    msg = Message(
        conversation_id=conv.id,
        platform_message_id=message_id,
        direction="out",
        sender_type="user",
        sender_name=current_user.display_name or current_user.email,
        text=text,
        sent_at=now,
    )
    db.session.add(msg)
    conv.last_message_at = now
    conv.last_message_text = text[:1000]
    db.session.commit()

    return jsonify({
        "ok": True,
        "message": {
            "id": msg.id,
            "platform_message_id": msg.platform_message_id,
            "direction": msg.direction,
            "sender_type": msg.sender_type,
            "sender_name": msg.sender_name,
            "text": msg.text,
            "sent_at": isoformat_or(msg.sent_at),
        },
    })


@inbox_bp.route(
    "/api/inbox/conversations/<int:conversation_id>/ai-suggest", methods=["POST"]
)
@login_required
def api_conversation_ai_suggest(conversation_id: int):
    """Draft an AI reply using the thread's most recent messages as context."""
    import logging
    log = logging.getLogger("socialposter")

    team_id = get_current_team_id(current_user.id)
    conv = Conversation.query.filter_by(id=conversation_id).first_or_404()
    if team_id and conv.team_id and conv.team_id != team_id:
        return jsonify({"error": "Conversation not in current team"}), 403

    data = request.get_json(silent=True) or {}
    tone = (data.get("tone") or "friendly").strip() or "friendly"
    provider_name = (data.get("provider") or "").strip() or None
    model_id = (data.get("model") or "").strip() or None
    temperature = data.get("temperature")
    if temperature is not None:
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            temperature = None

    # Pull the last 6 messages oldest→newest as conversational context.
    recent = (
        Message.query.filter_by(conversation_id=conv.id)
        .order_by(Message.sent_at.desc(), Message.id.desc())
        .limit(6)
        .all()
    )
    recent.reverse()
    transcript_lines: list[str] = []
    for m in recent:
        role = "Customer" if m.direction == "in" else "You"
        transcript_lines.append(f"{role}: {m.text}")
    transcript = "\n".join(transcript_lines)

    last_inbound = next(
        (m for m in reversed(recent) if m.direction == "in"), None,
    )
    if last_inbound is None:
        return jsonify({
            "error": "No inbound message in this conversation to reply to",
        }), 400

    try:
        from socialposter.core.ai_service import suggest_reply
        text = suggest_reply(
            comment_text=last_inbound.text,
            author_name=conv.participant_name or "",
            platform=conv.platform,
            post_text=transcript,
            tone=tone,
            provider_name=provider_name,
            model_id=model_id,
            temperature=temperature,
            user_id=current_user.id,
        )
        return jsonify({"text": text})
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        log.exception("AI conversation suggest failed")
        return jsonify({"error": f"AI request failed: {e}"}), 502


@inbox_bp.route("/api/inbox/stats")
@login_required
def api_inbox_stats():
    team_id = get_current_team_id(current_user.id)

    query = db.session.query(
        InboxComment.platform, func.count(InboxComment.id)
    ).filter(InboxComment.is_read == False)  # noqa: E712

    if team_id:
        query = query.filter(InboxComment.team_id == team_id)

    rows = query.group_by(InboxComment.platform).all()
    unread = {r[0]: r[1] for r in rows}
    total_unread = sum(unread.values())

    # Unread message counts per platform from Conversation.
    msg_query = db.session.query(
        Conversation.platform, func.sum(Conversation.unread_count),
    ).filter(Conversation.unread_count > 0)
    if team_id:
        msg_query = msg_query.filter(Conversation.team_id == team_id)
    else:
        msg_query = msg_query.filter(Conversation.team_id == None)  # noqa: E711
    msg_rows = msg_query.group_by(Conversation.platform).all()
    unread_messages = {r[0]: int(r[1] or 0) for r in msg_rows}
    total_unread_messages = sum(unread_messages.values())

    return jsonify({
        "unread": unread,
        "total_unread": total_unread,
        "unread_messages": unread_messages,
        "total_unread_messages": total_unread_messages,
    })
