"""Unified inbox blueprint – view/reply to comments across platforms."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from socialposter.utils.datetime import isoformat_or
from socialposter.utils.pagination import paginate_query
from socialposter.utils.team import get_current_team_id
from socialposter.web.models import InboxComment, db
from socialposter.web.permissions import team_required

inbox_bp = Blueprint("inbox", __name__)


@inbox_bp.route("/inbox")
@login_required
def inbox_page():
    return render_template("inbox.html")


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

    return jsonify({"unread": unread, "total_unread": total_unread})
