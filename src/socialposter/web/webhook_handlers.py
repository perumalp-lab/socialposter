"""Per-platform webhook event handlers.

Each handler receives the parsed payload and is responsible for translating
platform-specific shapes into our internal models (InboxComment, etc.).

All handlers are idempotent — duplicate deliveries (same comment_id) silently
no-op via the unique constraint on (platform, platform_comment_id).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from socialposter.web.models import (
    Conversation,
    InboxComment,
    Message,
    PublishedPost,
    db,
)

log = logging.getLogger("socialposter")


def _to_dt(value) -> datetime | None:
    """Best-effort conversion of Meta/IG timestamps to UTC datetime."""
    if value is None:
        return None
    try:
        # Meta sends Unix epoch seconds. IG sometimes sends ISO strings.
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        if isinstance(value, str):
            if value.isdigit():
                return datetime.fromtimestamp(int(value), tz=timezone.utc)
            # ISO 8601 (Instagram): "2026-05-01T12:00:00+0000"
            cleaned = value.replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError, OSError):
        return None
    return None


def _team_id_for(platform: str, platform_post_id: str) -> int | None:
    """Look up the team_id from a PublishedPost matching this comment's post."""
    if not platform_post_id:
        return None
    pp = PublishedPost.query.filter_by(
        platform=platform, platform_post_id=platform_post_id,
    ).first()
    return pp.team_id if pp else None


def _post_url_for(platform: str, platform_post_id: str) -> str:
    if not platform_post_id:
        return ""
    pp = PublishedPost.query.filter_by(
        platform=platform, platform_post_id=platform_post_id,
    ).first()
    return pp.platform_post_url if pp else ""


def _upsert_comment(
    *,
    platform: str,
    comment_id: str,
    post_id: str,
    text: str,
    author_name: str = "",
    author_profile_url: str = "",
    author_avatar_url: str = "",
    parent_comment_id: str | None = None,
    posted_at: datetime | None = None,
) -> InboxComment | None:
    """Create-or-skip InboxComment by (platform, platform_comment_id)."""
    if not comment_id:
        return None

    existing = InboxComment.query.filter_by(
        platform=platform, platform_comment_id=comment_id,
    ).first()
    if existing:
        return existing

    row = InboxComment(
        team_id=_team_id_for(platform, post_id),
        platform=platform,
        platform_comment_id=comment_id,
        platform_post_id=post_id or "",
        platform_post_url=_post_url_for(platform, post_id),
        author_name=author_name or "",
        author_profile_url=author_profile_url or "",
        author_avatar_url=author_avatar_url or "",
        text=text or "",
        parent_comment_id=parent_comment_id,
        is_read=False,
        fetched_at=datetime.now(timezone.utc),
        posted_at=posted_at,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        # Race with a concurrent delivery — refresh and ignore.
        db.session.rollback()
        return InboxComment.query.filter_by(
            platform=platform, platform_comment_id=comment_id,
        ).first()
    return row


# ── Per-platform dispatchers ──


def handle_facebook_event(payload: dict) -> int:
    """Ingest Facebook Page `feed` change events. Returns # comments stored."""
    if not isinstance(payload, dict):
        return 0
    stored = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "feed":
                continue
            value = change.get("value") or {}
            if value.get("item") != "comment":
                continue
            if value.get("verb") not in (None, "add", "edited"):
                continue

            from_user = value.get("from") or {}
            row = _upsert_comment(
                platform="facebook",
                comment_id=str(value.get("comment_id") or ""),
                post_id=str(value.get("post_id") or value.get("parent_id") or ""),
                text=value.get("message") or "",
                author_name=from_user.get("name") or "",
                parent_comment_id=str(value.get("parent_id"))
                if value.get("parent_id")
                else None,
                posted_at=_to_dt(value.get("created_time")),
            )
            if row is not None:
                stored += 1
    return stored


def handle_instagram_event(payload: dict) -> int:
    """Ingest Instagram `comments` change events."""
    if not isinstance(payload, dict):
        return 0
    stored = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") not in ("comments", "live_comments"):
                continue
            value = change.get("value") or {}
            from_user = value.get("from") or {}
            media = value.get("media") or {}
            row = _upsert_comment(
                platform="instagram",
                comment_id=str(value.get("id") or ""),
                post_id=str(media.get("id") or value.get("media_id") or ""),
                text=value.get("text") or "",
                author_name=from_user.get("username") or from_user.get("name") or "",
                parent_comment_id=str(value.get("parent_id"))
                if value.get("parent_id")
                else None,
                posted_at=_to_dt(value.get("created_time") or value.get("timestamp")),
            )
            if row is not None:
                stored += 1
    return stored


def _upsert_message(
    *,
    platform: str,
    thread_id: str,
    message_id: str,
    text: str,
    direction: str = "in",
    sender_type: str = "customer",
    sender_name: str = "",
    participant_id: str = "",
    participant_name: str = "",
    sent_at: datetime | None = None,
    team_id: int | None = None,
) -> Message | None:
    """Find-or-create the Conversation, then create-or-skip the Message."""
    if not thread_id or not message_id:
        return None

    conv = Conversation.query.filter_by(
        platform=platform, platform_thread_id=thread_id,
    ).first()
    if conv is None:
        conv = Conversation(
            team_id=team_id,
            platform=platform,
            platform_thread_id=thread_id,
            participant_id=participant_id or thread_id,
            participant_name=participant_name or thread_id,
        )
        db.session.add(conv)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            conv = Conversation.query.filter_by(
                platform=platform, platform_thread_id=thread_id,
            ).first()
            if conv is None:
                return None

    existing = Message.query.filter_by(
        conversation_id=conv.id, platform_message_id=message_id,
    ).first()
    if existing:
        return existing

    when = sent_at or datetime.now(timezone.utc)
    # SQLAlchemy DateTime columns drop tzinfo on read in SQLite, so normalise
    # to naive UTC for safe comparison and storage consistency.
    when_naive = when.astimezone(timezone.utc).replace(tzinfo=None) if when.tzinfo else when

    msg = Message(
        conversation_id=conv.id,
        platform_message_id=message_id,
        direction=direction,
        sender_type=sender_type,
        sender_name=sender_name or participant_name,
        text=text or "",
        sent_at=when_naive,
    )
    db.session.add(msg)

    # Roll up onto the conversation row.
    if direction == "in":
        conv.unread_count = (conv.unread_count or 0) + 1
    if conv.last_message_at is None or when_naive >= conv.last_message_at:
        conv.last_message_at = when_naive
        conv.last_message_text = (text or "")[:1000]
    if participant_name and not conv.participant_name:
        conv.participant_name = participant_name

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return Message.query.filter_by(
            conversation_id=conv.id, platform_message_id=message_id,
        ).first()
    return msg


def handle_youtube_event(payload: dict) -> int:
    """Acknowledge a YouTube PubSubHubbub Atom feed entry.

    The XML body is converted to a dict by webhook_routes._atom_to_dict, with
    namespaces flattened. Each `entry` child of the feed root represents a new
    or updated video. We don't persist these into our existing models — there
    is no PublishedPost row for a third party's upload — but we acknowledge
    the event by counting it so admins can confirm subscriptions are alive.

    Returns the number of video entries acknowledged.
    """
    if not isinstance(payload, dict):
        return 0
    if payload.get("tag") != "feed":
        return 0
    children = payload.get("children") or []
    if not isinstance(children, list):
        return 0

    count = 0
    for child in children:
        if isinstance(child, dict) and child.get("tag") == "entry":
            count += 1
    return count


def handle_linkedin_event(payload: dict) -> int:
    """Ingest LinkedIn social-actions webhook events.

    Payload shape (sparse — LinkedIn typically requires follow-up GETs to
    flesh out author profiles):
      {
        "eventType": "COMMENT_CREATED",
        "comment": {
          "id": "urn:li:comment:(activity:7XYZ,1234567890)",
          "actor": "urn:li:person:abc",        # author URN
          "object": "urn:li:activity:7XYZ",    # parent post URN
          "message": {"text": "Great!"},
          "createdAt": 1714600000000           # ms epoch
        }
      }
    """
    if not isinstance(payload, dict):
        return 0
    event_type = (payload.get("eventType") or payload.get("event") or "").upper()
    if event_type and event_type not in ("COMMENT_CREATED", "COMMENT_UPDATED"):
        return 0

    comment = payload.get("comment") or {}
    if not isinstance(comment, dict):
        return 0

    comment_id = str(comment.get("id") or "")
    if not comment_id:
        return 0

    actor = str(comment.get("actor") or "")
    text = ""
    msg = comment.get("message")
    if isinstance(msg, dict):
        text = msg.get("text", "") or ""
    elif isinstance(msg, str):
        text = msg

    post_id = str(comment.get("object") or "")
    created_ms = comment.get("createdAt")
    posted_at: datetime | None = None
    if isinstance(created_ms, (int, float)):
        try:
            posted_at = datetime.fromtimestamp(int(created_ms) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            posted_at = None

    # LinkedIn doesn't include the human display name in the webhook payload.
    # Fall back to the URN tail so the row is at least labelable.
    author_name = actor.rsplit(":", 1)[-1] if actor else ""

    row = _upsert_comment(
        platform="linkedin",
        comment_id=comment_id,
        post_id=post_id,
        text=text,
        author_name=author_name,
        author_profile_url=(
            f"https://www.linkedin.com/in/{author_name}" if author_name else ""
        ),
        posted_at=posted_at,
    )
    return 1 if row is not None else 0


def handle_twitter_event(payload: dict) -> int:
    """Ingest Twitter Account Activity direct-message events.

    Payload shape:
      for_user_id: "<bot_user_id>"
      direct_message_events: [{
        type: "message_create",
        id: "<msg_id>",
        created_timestamp: "<ms_epoch>",
        message_create: {
          target: {recipient_id},
          sender_id,
          message_data: {text}
        }
      }]
      users: {<id>: {id, name, screen_name, profile_image_url_https}}
    """
    if not isinstance(payload, dict):
        return 0
    bot_user_id = str(payload.get("for_user_id") or "")
    users = payload.get("users") or {}
    if not isinstance(users, dict):
        users = {}

    stored = 0
    for event in payload.get("direct_message_events") or []:
        if not isinstance(event, dict):
            continue
        if event.get("type") != "message_create":
            continue

        message_create = event.get("message_create") or {}
        sender_id = str(message_create.get("sender_id") or "")
        target = message_create.get("target") or {}
        recipient_id = str(target.get("recipient_id") or "")
        text = (message_create.get("message_data") or {}).get("text", "")

        # Determine direction: outbound if our user (the bot) sent it.
        is_outbound = bool(bot_user_id) and sender_id == bot_user_id
        # Thread is keyed by the *other* party in either direction.
        other_id = recipient_id if is_outbound else sender_id
        if not other_id:
            continue

        other_info = users.get(other_id) or {}
        sender_info = users.get(sender_id) or {}
        ts_ms = event.get("created_timestamp")
        sent_at: datetime | None = None
        if ts_ms is not None:
            try:
                sent_at = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                sent_at = None

        row = _upsert_message(
            platform="twitter",
            thread_id=other_id,
            message_id=str(event.get("id") or ""),
            text=text,
            direction="out" if is_outbound else "in",
            sender_type="user" if is_outbound else "customer",
            sender_name=sender_info.get("name") or sender_info.get("screen_name") or "",
            participant_id=other_id,
            participant_name=other_info.get("name") or other_info.get("screen_name") or "",
            sent_at=sent_at,
        )
        if row is not None:
            stored += 1
    return stored


def handle_whatsapp_event(payload: dict) -> int:
    """Ingest WhatsApp Cloud API messages.

    Payload shape:
      entry[].changes[]
        .field == "messages"
        .value
          .contacts[]: [{wa_id, profile.name}]
          .messages[]: [{id, from, text.body|...|, timestamp, type}]
    """
    if not isinstance(payload, dict):
        return 0
    stored = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            contacts = {
                c.get("wa_id"): (c.get("profile") or {}).get("name", "")
                for c in (value.get("contacts") or [])
                if isinstance(c, dict) and c.get("wa_id")
            }
            for message in value.get("messages") or []:
                if not isinstance(message, dict):
                    continue
                msg_type = message.get("type") or "text"
                # Extract human-readable text from common message types.
                if msg_type == "text":
                    text = (message.get("text") or {}).get("body", "")
                elif msg_type == "image":
                    text = "[image] " + ((message.get("image") or {}).get("caption", "") or "")
                elif msg_type == "video":
                    text = "[video] " + ((message.get("video") or {}).get("caption", "") or "")
                elif msg_type == "document":
                    text = "[document] " + ((message.get("document") or {}).get("filename", "") or "")
                elif msg_type == "audio":
                    text = "[audio]"
                elif msg_type == "interactive":
                    interactive = message.get("interactive") or {}
                    sub = interactive.get("type")
                    if sub == "button_reply":
                        text = (interactive.get("button_reply") or {}).get("title", "")
                    elif sub == "list_reply":
                        text = (interactive.get("list_reply") or {}).get("title", "")
                    else:
                        text = f"[interactive:{sub}]"
                else:
                    text = f"[{msg_type}]"

                from_id = message.get("from") or ""
                row = _upsert_message(
                    platform="whatsapp",
                    thread_id=str(from_id),
                    message_id=str(message.get("id") or ""),
                    text=text,
                    direction="in",
                    sender_type="customer",
                    sender_name=contacts.get(from_id, ""),
                    participant_id=str(from_id),
                    participant_name=contacts.get(from_id, ""),
                    sent_at=_to_dt(message.get("timestamp")),
                )
                if row is not None:
                    stored += 1
    return stored


# Public dispatcher used by webhook_routes._dispatch
def dispatch(platform: str, payload: dict | None) -> dict:
    """Route a payload to the right handler. Returns a small summary dict."""
    if not payload:
        return {"handled": False, "stored": 0}

    if platform in ("facebook", "meta"):
        # `meta` is sometimes used as the umbrella platform. Inspect payload's
        # `object` field to disambiguate (page=facebook, instagram=instagram).
        obj = payload.get("object") if isinstance(payload, dict) else None
        if obj == "instagram":
            return {"handled": True, "stored": handle_instagram_event(payload)}
        return {"handled": True, "stored": handle_facebook_event(payload)}

    if platform == "instagram":
        return {"handled": True, "stored": handle_instagram_event(payload)}

    if platform == "whatsapp":
        return {"handled": True, "stored": handle_whatsapp_event(payload)}

    if platform == "twitter":
        return {"handled": True, "stored": handle_twitter_event(payload)}

    if platform == "linkedin":
        return {"handled": True, "stored": handle_linkedin_event(payload)}

    if platform == "youtube":
        return {"handled": True, "stored": handle_youtube_event(payload)}

    return {"handled": False, "stored": 0}
