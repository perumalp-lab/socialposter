"""Per-user AI configuration API — 'bring your own key'."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from socialposter.utils.datetime import isoformat_or
from socialposter.web.models import UserAIConfig, db
from socialposter.web.token_auth import token_or_session_required

user_ai_bp = Blueprint("user_ai", __name__, url_prefix="/api/user/ai")

VALID_PROVIDERS = {"claude", "openai", "gemini", "perplexity"}


@user_ai_bp.route("/configs", methods=["GET"])
@token_or_session_required
def list_configs():
    """List the current user's AI provider configs."""
    configs = UserAIConfig.query.filter_by(user_id=current_user.id).all()
    return jsonify([
        {
            "id": c.id,
            "provider_name": c.provider_name,
            "model_id": c.model_id,
            "is_active": c.is_active,
            "has_key": bool(c.api_key),
            "created_at": isoformat_or(c.created_at),
        }
        for c in configs
    ])


@user_ai_bp.route("/configs", methods=["POST"])
@token_or_session_required
def save_config():
    """Create or update an AI provider config for the current user."""
    data = request.get_json(silent=True) or {}
    provider_name = (data.get("provider_name") or "").strip().lower()
    api_key = (data.get("api_key") or "").strip()
    model_id = (data.get("model_id") or "").strip() or None
    is_active = data.get("is_active", True)

    if provider_name not in VALID_PROVIDERS:
        return jsonify({"error": f"Invalid provider. Choose from: {', '.join(sorted(VALID_PROVIDERS))}"}), 400
    if not api_key:
        return jsonify({"error": "API key is required"}), 400

    existing = UserAIConfig.query.filter_by(
        user_id=current_user.id, provider_name=provider_name
    ).first()

    if existing:
        existing.api_key = api_key
        existing.model_id = model_id
        existing.is_active = is_active
    else:
        existing = UserAIConfig(
            user_id=current_user.id,
            provider_name=provider_name,
            model_id=model_id,
            is_active=is_active,
        )
        existing.api_key = api_key
        db.session.add(existing)

    db.session.commit()
    return jsonify({"ok": True, "id": existing.id})


@user_ai_bp.route("/configs/<int:config_id>", methods=["DELETE"])
@token_or_session_required
def delete_config(config_id: int):
    """Remove a user AI config."""
    config = UserAIConfig.query.filter_by(
        id=config_id, user_id=current_user.id
    ).first()
    if not config:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(config)
    db.session.commit()
    return jsonify({"ok": True})
