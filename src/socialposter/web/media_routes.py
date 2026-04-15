"""Media Library blueprint – upload, browse, tag, and manage media assets."""

from __future__ import annotations

import mimetypes
import os
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from socialposter.utils.pagination import paginate_query
from socialposter.utils.team import get_current_team_id
from socialposter.web.models import MediaAsset, db
from socialposter.web.token_auth import token_or_session_required

DATA_DIR = Path(os.environ.get("SOCIALPOSTER_DATA_DIR", str(Path.home() / ".socialposter")))
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

media_bp = Blueprint("media", __name__)


@media_bp.route("/media")
@login_required
def media_page():
    """Serve the media library UI."""
    return render_template("media.html")


@media_bp.route("/api/media", methods=["GET"])
@token_or_session_required
def api_media_list():
    """List media assets with optional filters and pagination."""
    page = request.args.get("page", 1, type=int)
    media_type = request.args.get("type", "")
    tag = request.args.get("tag", "")
    search = request.args.get("search", "")

    query = MediaAsset.query.filter(MediaAsset.user_id == current_user.id)

    if media_type:
        query = query.filter(MediaAsset.media_type == media_type)
    if tag:
        query = query.filter(MediaAsset.tags.contains(tag))
    if search:
        query = query.filter(MediaAsset.filename.ilike(f"%{search}%"))

    query = query.order_by(MediaAsset.created_at.desc())

    def _serialize(m):
        return {
            "id": m.id,
            "filename": m.filename,
            "file_path": m.file_path,
            "media_type": m.media_type,
            "mime_type": m.mime_type,
            "file_size": m.file_size,
            "tags": m.tags or [],
            "alt_text": m.alt_text,
            "usage_count": m.usage_count,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }

    return jsonify(paginate_query(query, page, per_page=24, serializer=_serialize))


@media_bp.route("/api/media/upload", methods=["POST"])
@token_or_session_required
def api_media_upload():
    """Upload a media file to the library."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / unique_name
    file.save(str(save_path))

    # Determine media type
    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
    if ext in video_exts:
        media_type = "video"
    elif ext in image_exts:
        media_type = "image"
    else:
        media_type = "document"

    mime = mimetypes.guess_type(file.filename)[0] or ""
    file_size = save_path.stat().st_size

    asset = MediaAsset(
        team_id=get_current_team_id(current_user.id),
        user_id=current_user.id,
        filename=file.filename,
        file_path=str(save_path),
        media_type=media_type,
        mime_type=mime,
        file_size=file_size,
        tags=[],
        alt_text="",
    )
    db.session.add(asset)
    db.session.commit()

    return jsonify({
        "ok": True,
        "id": asset.id,
        "path": str(save_path),
        "filename": file.filename,
        "media_type": media_type,
        "file_size": file_size,
    })


@media_bp.route("/api/media/<int:media_id>", methods=["DELETE"])
@token_or_session_required
def api_media_delete(media_id: int):
    """Delete a media asset."""
    asset = MediaAsset.query.filter_by(
        id=media_id, user_id=current_user.id
    ).first()
    if not asset:
        return jsonify({"error": "Not found"}), 404

    # Remove file from disk
    try:
        path = Path(asset.file_path)
        if path.exists():
            path.unlink()
    except Exception:
        pass

    db.session.delete(asset)
    db.session.commit()
    return jsonify({"ok": True})


@media_bp.route("/api/media/<int:media_id>/tags", methods=["PUT"])
@token_or_session_required
def api_media_tags(media_id: int):
    """Update tags for a media asset."""
    asset = MediaAsset.query.filter_by(
        id=media_id, user_id=current_user.id
    ).first()
    if not asset:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    tags = data.get("tags", [])
    alt_text = data.get("alt_text")

    if isinstance(tags, list):
        asset.tags = [str(t).strip() for t in tags if str(t).strip()]
    if alt_text is not None:
        asset.alt_text = str(alt_text).strip()

    db.session.commit()
    return jsonify({"ok": True, "tags": asset.tags, "alt_text": asset.alt_text})
