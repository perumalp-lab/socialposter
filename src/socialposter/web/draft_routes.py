"""Draft/approval workflow blueprint – create, review, approve, publish drafts."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, render_template, request
from flask_login import current_user, login_required

from socialposter.core.content import (
    DefaultContent,
    MediaItem,
    PlatformOverrides,
    PostFile,
)
from socialposter.core.publisher import _publish_one, _resolve_platforms
from socialposter.utils.publishing import build_platform_overrides, record_published_post
from socialposter.web.models import (
    DraftComment,
    DraftPost,
    db,
    record_post_history,
)
from socialposter.web.permissions import role_required, team_required

draft_bp = Blueprint("drafts", __name__)


@draft_bp.route("/drafts")
@login_required
@team_required
def drafts_page():
    return render_template("drafts.html")


@draft_bp.route("/drafts/<int:draft_id>")
@login_required
@team_required
def draft_detail_page(draft_id: int):
    draft = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    return render_template("draft_detail.html", draft=draft)


# ── CRUD ──


@draft_bp.route("/api/drafts", methods=["POST"])
@login_required
@team_required
@role_required("admin", "editor")
def create_draft():
    data = request.get_json(force=True) or {}
    draft = DraftPost(
        team_id=g.team.id,
        author_id=current_user.id,
        name=data.get("name", "Untitled Draft"),
        platforms=data.get("platforms", []),
        text=data.get("text", ""),
        media=data.get("media", []),
        overrides=data.get("overrides", {}),
        status="draft",
    )
    db.session.add(draft)
    db.session.commit()
    return jsonify({"ok": True, "id": draft.id}), 201


@draft_bp.route("/api/drafts", methods=["GET"])
@login_required
@team_required
def list_drafts():
    status_filter = request.args.get("status", "")
    query = DraftPost.query.filter_by(team_id=g.team.id)
    if status_filter:
        query = query.filter(DraftPost.status == status_filter)
    query = query.order_by(DraftPost.updated_at.desc())
    drafts = query.all()
    return jsonify({
        "items": [
            {
                "id": d.id,
                "name": d.name,
                "status": d.status,
                "platforms": d.platforms,
                "text": d.text[:200],
                "author": d.author.display_name if d.author else "",
                "updated_at": d.updated_at.isoformat() if d.updated_at else "",
            }
            for d in drafts
        ]
    })


@draft_bp.route("/api/drafts/<int:draft_id>", methods=["GET"])
@login_required
@team_required
def get_draft(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    return jsonify({
        "id": d.id,
        "name": d.name,
        "status": d.status,
        "platforms": d.platforms,
        "text": d.text,
        "media": d.media,
        "overrides": d.overrides,
        "author": d.author.display_name if d.author else "",
        "author_id": d.author_id,
        "reviewed_by": d.reviewer.display_name if d.reviewer else None,
        "review_comment": d.review_comment,
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else "",
        "updated_at": d.updated_at.isoformat() if d.updated_at else "",
        "comments": [
            {
                "id": c.id,
                "user": c.user.display_name if c.user else "",
                "text": c.text,
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in d.comments
        ],
    })


@draft_bp.route("/api/drafts/<int:draft_id>", methods=["PUT"])
@login_required
@team_required
@role_required("admin", "editor")
def update_draft(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    if d.status not in ("draft", "rejected"):
        return jsonify({"error": "Can only edit drafts or rejected posts"}), 400
    data = request.get_json(force=True) or {}
    if "name" in data:
        d.name = data["name"]
    if "platforms" in data:
        d.platforms = data["platforms"]
    if "text" in data:
        d.text = data["text"]
    if "media" in data:
        d.media = data["media"]
    if "overrides" in data:
        d.overrides = data["overrides"]
    d.status = "draft"
    db.session.commit()
    return jsonify({"ok": True})


@draft_bp.route("/api/drafts/<int:draft_id>", methods=["DELETE"])
@login_required
@team_required
@role_required("admin", "editor")
def delete_draft(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    db.session.delete(d)
    db.session.commit()
    return jsonify({"ok": True})


# ── Workflow ──


@draft_bp.route("/api/drafts/<int:draft_id>/submit", methods=["POST"])
@login_required
@team_required
@role_required("admin", "editor")
def submit_draft(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    if d.status not in ("draft", "rejected"):
        return jsonify({"error": "Only drafts or rejected posts can be submitted"}), 400
    d.status = "pending_approval"
    db.session.commit()
    return jsonify({"ok": True, "status": d.status})


@draft_bp.route("/api/drafts/<int:draft_id>/approve", methods=["POST"])
@login_required
@team_required
@role_required("admin")
def approve_draft(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    if d.status != "pending_approval":
        return jsonify({"error": "Only pending drafts can be approved"}), 400
    d.status = "approved"
    d.reviewed_by = current_user.id
    d.reviewed_at = datetime.now(timezone.utc)
    data = request.get_json(force=True) or {}
    d.review_comment = data.get("comment", "")
    db.session.commit()
    return jsonify({"ok": True, "status": d.status})


@draft_bp.route("/api/drafts/<int:draft_id>/reject", methods=["POST"])
@login_required
@team_required
@role_required("admin")
def reject_draft(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    if d.status != "pending_approval":
        return jsonify({"error": "Only pending drafts can be rejected"}), 400
    data = request.get_json(force=True) or {}
    d.status = "rejected"
    d.reviewed_by = current_user.id
    d.reviewed_at = datetime.now(timezone.utc)
    d.review_comment = data.get("comment", "Rejected")
    db.session.commit()
    return jsonify({"ok": True, "status": d.status})


@draft_bp.route("/api/drafts/<int:draft_id>/publish", methods=["POST"])
@login_required
@team_required
@role_required("admin", "editor")
def publish_draft(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    if d.status != "approved":
        return jsonify({"error": "Only approved drafts can be published"}), 400

    # Build PostFile from draft
    media_items = []
    for m in (d.media or []):
        media_items.append(
            MediaItem(path=m["path"], type=m.get("media_type", "image"), alt_text=m.get("alt_text"))
        )
    defaults = DefaultContent(text=d.text, media=media_items)

    overrides_kwargs = build_platform_overrides(d.platforms, d.overrides or {})
    content = PostFile(defaults=defaults, platforms=PlatformOverrides(**overrides_kwargs))
    platforms = _resolve_platforms(content, d.platforms)

    results = []
    for platform in platforms:
        try:
            result = _publish_one(platform, content, dry_run=False, user_id=current_user.id)
            results.append({
                "platform": result.platform,
                "success": result.success,
                "post_id": result.post_id,
                "post_url": result.post_url,
                "error": result.error_message,
            })
            record_post_history(
                user_id=current_user.id,
                platform=result.platform,
                text=d.text,
                success=result.success,
                media=d.media,
                post_id=result.post_id,
                post_url=result.post_url,
                error_message=result.error_message,
            )
            if result.success and result.post_id:
                record_published_post(
                    user_id=current_user.id,
                    team_id=g.team.id,
                    result=result,
                    text_preview=d.text or "",
                )
        except Exception as e:
            results.append({
                "platform": platform.name,
                "success": False,
                "post_id": None,
                "post_url": None,
                "error": str(e),
            })

    d.status = "published"
    db.session.commit()
    return jsonify({"ok": True, "results": results})


# ── Comments ──


@draft_bp.route("/api/drafts/<int:draft_id>/comments", methods=["POST"])
@login_required
@team_required
def add_comment(draft_id: int):
    d = DraftPost.query.filter_by(id=draft_id, team_id=g.team.id).first_or_404()
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Comment text is required"}), 400

    comment = DraftComment(draft_id=d.id, user_id=current_user.id, text=text)
    db.session.add(comment)
    db.session.commit()
    return jsonify({
        "ok": True,
        "comment": {
            "id": comment.id,
            "user": current_user.display_name,
            "text": comment.text,
            "created_at": comment.created_at.isoformat() if comment.created_at else "",
        },
    })
