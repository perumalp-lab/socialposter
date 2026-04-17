"""Admin blueprint – OAuth app settings management."""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from socialposter.web.models import AppSetting, db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Keys managed by the admin settings page
OAUTH_KEYS = [
    ("meta_client_id", "Meta App ID", "Shared by Facebook, Instagram, WhatsApp"),
    ("meta_client_secret", "Meta App Secret", ""),
    ("linkedin_client_id", "LinkedIn Client ID", ""),
    ("linkedin_client_secret", "LinkedIn Client Secret", ""),
    ("google_client_id", "Google Client ID", "For YouTube OAuth"),
    ("google_client_secret", "Google Client Secret", ""),
    ("twitter_client_id", "Twitter/X Client ID", "OAuth 2.0 with PKCE"),
    ("twitter_client_secret", "Twitter/X Client Secret", ""),
]

AI_KEYS = [
    ("ai_provider", "AI Provider", "Claude (Anthropic) or OpenAI"),
    ("ai_claude_api_key", "Claude API Key", "From console.anthropic.com"),
    ("ai_openai_api_key", "OpenAI API Key", "From platform.openai.com"),
]


@admin_bp.before_request
@login_required
def require_admin():
    if not current_user.is_admin:
        flash("Admin access required.", "error")
        return redirect(url_for("main.index"))


@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        for key, _label, _hint in OAUTH_KEYS:
            value = request.form.get(key, "").strip()
            if value:
                AppSetting.set(key, value)
        # AI settings — always save ai_provider (even if default)
        for key, _label, _hint in AI_KEYS:
            value = request.form.get(key, "").strip()
            if key == "ai_provider":
                AppSetting.set(key, value or "claude")
            elif value:
                AppSetting.set(key, value)
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))

    current_values = {}
    for key, label, hint in OAUTH_KEYS:
        val = AppSetting.get(key)
        current_values[key] = {
            "label": label,
            "hint": hint,
            "value": val,
            "masked": _mask(val) if val else "",
        }
    for key, label, hint in AI_KEYS:
        val = AppSetting.get(key)
        current_values[key] = {
            "label": label,
            "hint": hint,
            "value": val,
            "masked": _mask(val) if val and key != "ai_provider" else val,
        }

    return render_template("admin.html", settings=current_values, keys=OAUTH_KEYS, ai_keys=AI_KEYS)


@admin_bp.route("/api/ai-providers", methods=["GET"])
def api_ai_providers_list():
    """List configured AI providers and their models."""
    from socialposter.web.models import AIProviderConfig
    providers = AIProviderConfig.query.all()
    result = []
    for p in providers:
        result.append({
            "id": p.id,
            "name": p.name,
            "display_name": p.display_name,
            "is_active": p.is_active,
            "has_key": bool(p._api_key),
            "models": [
                {
                    "id": m.id,
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "is_default": m.is_default,
                    "cost_tier": m.cost_tier,
                    "max_tokens": m.max_tokens,
                }
                for m in p.models
            ],
        })
    return jsonify(result)


@admin_bp.route("/api/ai-providers", methods=["POST"])
def api_ai_providers_save():
    """Create or update an AI provider config."""
    from socialposter.web.models import AIProviderConfig, AIModelConfig

    data = request.get_json(silent=True) if request.is_json else None
    if not data:
        # Handle form submission
        data = request.form.to_dict()

    name = (data.get("name") or "").strip().lower()
    display_name = (data.get("display_name") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    is_active = data.get("is_active") in (True, "true", "on", "1")

    if not name or not display_name:
        if request.is_json:
            return jsonify({"error": "name and display_name are required"}), 400
        flash("Provider name and display name are required.", "error")
        return redirect(url_for("admin.settings"))

    provider = AIProviderConfig.query.filter_by(name=name).first()
    if not provider:
        provider = AIProviderConfig(name=name, display_name=display_name)
        db.session.add(provider)
    else:
        provider.display_name = display_name

    if api_key:
        provider.api_key = api_key
    provider.is_active = is_active
    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True, "id": provider.id})
    flash(f"AI provider '{display_name}' saved.", "success")
    return redirect(url_for("admin.settings"))


def _mask(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 6) + value[-3:]


@admin_bp.route("/debug/database", methods=["GET"])
def debug_database():
    """Debug route to show database schema information."""
    import sqlalchemy
    from sqlalchemy import inspect
    
    info = {
        "database_url": str(db.engine.url).split("@")[0] + "@***",  # Hide credentials
        "dialect": db.engine.dialect.name,
    }
    
    # Get table and column information
    inspector = inspect(db.engine)
    info["tables"] = {}
    
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        info["tables"][table_name] = {}
        
        for col in columns:
            col_type = str(col["type"])
            col_length = getattr(col["type"], "length", None)
            info["tables"][table_name][col["name"]] = {
                "type": col_type,
                "length": col_length,
                "nullable": col.get("nullable", True),
            }
    
    return jsonify({
        "database": info,
        "warning": "This is debug information. Ensure this is only accessible to admins."
    })
