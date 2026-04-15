"""AI assistant API routes — content generation, optimization, hashtags."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from socialposter.web.token_auth import token_or_session_required

log = logging.getLogger("socialposter")

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@ai_bp.route("/models", methods=["GET"])
@token_or_session_required
def ai_models():
    """List available AI providers and models for the frontend selector."""
    try:
        from socialposter.web.models import AIProviderConfig
        providers = AIProviderConfig.query.filter_by(is_active=True).all()
        result = []
        for p in providers:
            for m in p.models:
                result.append({
                    "provider": p.name,
                    "provider_display": p.display_name,
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "is_default": m.is_default,
                    "cost_tier": m.cost_tier,
                })
        # If no database configs, return the default providers from AppSettings
        if not result:
            from socialposter.web.models import AppSetting
            active = AppSetting.get("ai_provider", "claude")
            result = [
                {"provider": active, "provider_display": active.title(),
                 "model_id": "", "display_name": f"Default ({active.title()})",
                 "is_default": True, "cost_tier": "standard"},
            ]
        return jsonify(result)
    except Exception as e:
        log.exception("Failed to list AI models")
        return jsonify([]), 200


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
        text = generate_content(topic, platforms, provider_name, model_id, temperature, user_id=current_user.id)
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
        result = optimize_for_platforms(text, platforms, provider_name, model_id, temperature, user_id=current_user.id)
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
        tags = suggest_hashtags(text, platform, count, provider_name, model_id, temperature, user_id=current_user.id)
        return jsonify({"hashtags": tags})
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        log.exception("AI hashtags failed")
        return jsonify({"error": f"AI request failed: {e}"}), 502
