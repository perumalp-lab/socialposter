"""AI assistant API routes — content generation, optimization, hashtags."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from socialposter.web.token_auth import token_or_session_required

log = logging.getLogger("socialposter")

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

SUPPORTED_PROVIDERS = ("claude", "openai", "gemini", "perplexity")

# Curated suggested model IDs surfaced in the picker. Users can also type
# any model ID into their per-user key row.
SUGGESTED_MODELS = {
    "claude": [
        ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5"),
        ("claude-opus-4-7", "Claude Opus 4.7"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
    ],
    "openai": [
        ("gpt-4o", "GPT-4o"),
        ("gpt-4o-mini", "GPT-4o mini"),
        ("o3-mini", "o3-mini"),
    ],
    "gemini": [
        ("gemini-2.0-flash", "Gemini 2.0 Flash"),
        ("gemini-1.5-pro", "Gemini 1.5 Pro"),
    ],
    "perplexity": [
        ("sonar", "Sonar"),
        ("sonar-pro", "Sonar Pro"),
    ],
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 6) + value[-3:]


@ai_bp.route("/models", methods=["GET"])
@token_or_session_required
def ai_models():
    """List AI providers + suggested models the current user can pick from.

    A provider is "available" if (a) the user has their own key for it, or
    (b) a workspace AIProviderConfig is active, or (c) the legacy
    ai_<provider>_api_key AppSetting is set.
    """
    from socialposter.web.models import (
        AIProviderConfig,
        AppSetting,
        UserAIKey,
    )

    user_keys: dict[str, UserAIKey] = {
        k.provider: k
        for k in UserAIKey.query.filter_by(user_id=current_user.id).all()
    }
    workspace = {
        p.name: p
        for p in AIProviderConfig.query.filter_by(is_active=True).all()
        if p.api_key
    }

    out = []
    for prov in SUPPORTED_PROVIDERS:
        from_user = prov in user_keys
        from_workspace = prov in workspace
        from_legacy = bool(AppSetting.get(f"ai_{prov}_api_key"))
        if not (from_user or from_workspace or from_legacy):
            continue

        # Pick model list: workspace-specified models if any, else suggested.
        models: list[dict] = []
        ws = workspace.get(prov)
        if ws and ws.models:
            for m in ws.models:
                models.append({
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "is_default": m.is_default,
                })
        else:
            for mid, label in SUGGESTED_MODELS.get(prov, []):
                models.append({
                    "model_id": mid,
                    "display_name": label,
                    "is_default": False,
                })

        out.append({
            "provider": prov,
            "provider_display": prov.title(),
            "models": models,
            "user_key_set": from_user,
            "user_default_model": user_keys[prov].default_model if from_user else None,
            "workspace_available": from_workspace or from_legacy,
        })

    user_default_provider = next(
        (k.provider for k in user_keys.values() if k.is_default), None,
    )
    fallback_provider = AppSetting.get("ai_provider", "claude")

    return jsonify({
        "providers": out,
        "default_provider": user_default_provider or fallback_provider,
    })


# ── Per-user key management ──


@ai_bp.route("/user-keys", methods=["GET"])
@token_or_session_required
def list_user_keys():
    from socialposter.web.models import UserAIKey
    rows = UserAIKey.query.filter_by(user_id=current_user.id).all()
    return jsonify([
        {
            "provider": r.provider,
            "default_model": r.default_model,
            "is_default": r.is_default,
            "masked": _mask(r.api_key),
        }
        for r in rows
    ])


@ai_bp.route("/user-keys/<provider>", methods=["PUT"])
@token_or_session_required
def upsert_user_key(provider: str):
    from socialposter.web.models import UserAIKey, db
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({"error": "Unsupported provider"}), 400
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    default_model = (data.get("default_model") or "").strip() or None

    row = UserAIKey.query.filter_by(
        user_id=current_user.id, provider=provider
    ).first()

    if row is None:
        if not api_key:
            return jsonify({"error": "api_key required to create a new entry"}), 400
        row = UserAIKey(user_id=current_user.id, provider=provider)
        db.session.add(row)

    if api_key:
        row.api_key = api_key
    if "default_model" in data:
        row.default_model = default_model

    # First key auto-becomes default for the user.
    if not row.is_default:
        existing_default = (
            UserAIKey.query.filter_by(user_id=current_user.id, is_default=True)
            .filter(UserAIKey.id != row.id)
            .first()
        )
        if existing_default is None:
            row.is_default = True

    db.session.commit()
    return jsonify({
        "ok": True,
        "provider": row.provider,
        "default_model": row.default_model,
        "is_default": row.is_default,
        "masked": _mask(row.api_key),
    })


@ai_bp.route("/user-keys/<provider>", methods=["DELETE"])
@token_or_session_required
def delete_user_key(provider: str):
    from socialposter.web.models import UserAIKey, db
    row = UserAIKey.query.filter_by(
        user_id=current_user.id, provider=provider
    ).first()
    if not row:
        return jsonify({"ok": True})
    was_default = row.is_default
    db.session.delete(row)
    db.session.commit()
    # Promote another user key to default if one exists.
    if was_default:
        next_row = UserAIKey.query.filter_by(user_id=current_user.id).first()
        if next_row:
            next_row.is_default = True
            db.session.commit()
    return jsonify({"ok": True})


@ai_bp.route("/user-keys/<provider>/default", methods=["POST"])
@token_or_session_required
def set_default_user_key(provider: str):
    from socialposter.web.models import UserAIKey, db
    row = UserAIKey.query.filter_by(
        user_id=current_user.id, provider=provider
    ).first()
    if not row:
        return jsonify({"error": "Provider not configured for this user"}), 404
    UserAIKey.query.filter_by(user_id=current_user.id).update(
        {"is_default": False}, synchronize_session=False,
    )
    row.is_default = True
    db.session.commit()
    return jsonify({"ok": True})


@ai_bp.route("/preferences", methods=["GET"])
@token_or_session_required
def ai_preferences_get():
    """Return workspace-level AI preferences (read-only for non-admins)."""
    from socialposter.web.models import AppSetting
    raw = (AppSetting.get("ai_cost_optimization") or "").strip().lower()
    return jsonify({
        "cost_optimization": raw in ("1", "true", "yes", "on"),
    })


@ai_bp.route("/preferences", methods=["PUT"])
@token_or_session_required
def ai_preferences_put():
    """Update workspace-level AI preferences. Admin-only."""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Admin access required"}), 403
    from socialposter.web.models import AppSetting
    data = request.get_json(silent=True) or {}
    if "cost_optimization" in data:
        AppSetting.set(
            "ai_cost_optimization",
            "true" if bool(data["cost_optimization"]) else "false",
        )
    raw = (AppSetting.get("ai_cost_optimization") or "").strip().lower()
    return jsonify({
        "ok": True,
        "cost_optimization": raw in ("1", "true", "yes", "on"),
    })


@ai_bp.route("/generate", methods=["POST"])
@token_or_session_required
def ai_generate():
    """Generate a social media post from a topic."""
    from socialposter.core.ai_service import generate_content

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    platforms = data.get("platforms") or []

    provider_name = (data.get("provider") or "").strip() or None
    model_id = (data.get("model") or "").strip() or None
    temperature = data.get("temperature")
    if temperature is not None:
        temperature = float(temperature)

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    try:
        text = generate_content(
            topic, platforms, provider_name, model_id, temperature,
            user_id=current_user.id,
        )
        return jsonify({"text": text})
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        log.exception("AI generate failed")
        return jsonify({"error": f"AI request failed: {e}"}), 502


@ai_bp.route("/generate-structured", methods=["POST"])
@token_or_session_required
def ai_generate_structured():
    """Generate structured content: caption, hashtags, image idea, CTA."""
    from socialposter.core.ai_service import generate_structured_content

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    platforms = data.get("platforms") or []
    audience = (data.get("audience") or "").strip()
    goal = (data.get("goal") or "").strip()
    tone = (data.get("tone") or "").strip()

    provider_name = (data.get("provider") or "").strip() or None
    model_id = (data.get("model") or "").strip() or None
    temperature = data.get("temperature")
    if temperature is not None:
        temperature = float(temperature)

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    try:
        result = generate_structured_content(
            topic, platforms, audience, goal, tone,
            provider_name, model_id, temperature,
            user_id=current_user.id,
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        log.exception("AI structured generate failed")
        return jsonify({"error": f"AI request failed: {e}"}), 502


@ai_bp.route("/optimize", methods=["POST"])
@token_or_session_required
def ai_optimize():
    """Rewrite text optimized for each selected platform."""
    from socialposter.core.ai_service import optimize_for_platforms

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    platforms = data.get("platforms") or []

    provider_name = (data.get("provider") or "").strip() or None
    model_id = (data.get("model") or "").strip() or None
    temperature = data.get("temperature")
    if temperature is not None:
        temperature = float(temperature)

    if not text:
        return jsonify({"error": "Text is required"}), 400
    if not platforms:
        return jsonify({"error": "At least one platform is required"}), 400

    try:
        result = optimize_for_platforms(
            text, platforms, provider_name, model_id, temperature,
            user_id=current_user.id,
        )
        return jsonify({"optimized": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        log.exception("AI optimize failed")
        return jsonify({"error": f"AI request failed: {e}"}), 502


@ai_bp.route("/hashtags", methods=["POST"])
@token_or_session_required
def ai_hashtags():
    """Suggest hashtags for a given text and platform."""
    from socialposter.core.ai_service import suggest_hashtags

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    platform = (data.get("platform") or "").strip()
    count = data.get("count", 5)

    provider_name = (data.get("provider") or "").strip() or None
    model_id = (data.get("model") or "").strip() or None
    temperature = data.get("temperature")
    if temperature is not None:
        temperature = float(temperature)

    if not text:
        return jsonify({"error": "Text is required"}), 400
    if not platform:
        return jsonify({"error": "Platform is required"}), 400

    try:
        tags = suggest_hashtags(
            text, platform, count, provider_name, model_id, temperature,
            user_id=current_user.id,
        )
        return jsonify({"hashtags": tags})
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        log.exception("AI hashtags failed")
        return jsonify({"error": f"AI request failed: {e}"}), 502
