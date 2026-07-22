"""Flask web UI for Kryptams – compose & publish posts via the browser."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, Blueprint, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, current_user, login_required
from flask_wtf.csrf import CSRFProtect

from socialposter.core.content import (
    DefaultContent,
    MediaItem,
    MediaType,
    PlatformOverrides,
    PostFile,
    PLATFORM_TEXT_LIMITS,
)
from socialposter.core.publisher import publish_all, _resolve_platforms, _publish_one
from socialposter.platforms.registry import PlatformRegistry
from socialposter.utils.publishing import build_platform_overrides, record_published_post
from socialposter.utils.team import get_current_team_id
from socialposter.web.token_auth import token_or_session_required

# Ensure all platform plugins are imported / registered
import socialposter.platforms  # noqa: F401

# Upload destination — overridable via env so prod can mount a persistent
# disk (Render etc.) instead of using the user's home dir.
UPLOAD_DIR = Path(
    os.environ.get("SOCIALPOSTER_UPLOAD_DIR")
    or (Path.home() / ".socialposter" / "uploads")
)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Main blueprint – existing routes live here
# ---------------------------------------------------------------------------

main_bp = Blueprint("main", __name__)


# NOTE: Old Jinja UI routes (/, /connections, etc.) were removed when the
# React SPA took over the browser UI. The catch-all in this file serves the
# SPA for any non-API path. Page state lives in /api/* JSON endpoints below.


_ALLOWED_CONFIG_KEYS = {
    "whatsapp": ["phone_number_id"],
    "facebook": ["page_id"],
    "instagram": ["business_account_id"],
}


@main_bp.route("/api/connection/<platform>/config", methods=["POST"])
@token_or_session_required
def api_connection_config(platform: str):
    """Save platform-specific config values into PlatformConnection.extra_data."""
    import logging
    from socialposter.web.models import db

    log = logging.getLogger("socialposter")

    allowed = _ALLOWED_CONFIG_KEYS.get(platform)
    if allowed is None:
        return jsonify({"error": f"No configurable keys for {platform}"}), 400

    conn = current_user.get_connection(platform)
    if conn is None:
        return jsonify({"error": f"Not connected to {platform}"}), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    extra = dict(conn.extra_data or {})
    updated_keys = []
    for key in allowed:
        if key in data:
            value = str(data[key]).strip()
            if not value:
                return jsonify({"error": f"{key} cannot be empty"}), 422
            extra[key] = value
            updated_keys.append(key)

    if not updated_keys:
        return jsonify({"error": "No recognised keys provided"}), 400

    conn.extra_data = extra
    db.session.commit()
    log.info("User %s updated %s config: %s", current_user.id, platform, updated_keys)

    from socialposter.web.models import log_activity
    log_activity(
        current_user.id,
        "connection.config_update",
        target_type="connection",
        target_id=platform,
        details={"updated_keys": updated_keys},
    )

    return jsonify({"ok": True, "extra_data": extra})


@main_bp.route("/api/platforms", methods=["GET"])
@token_or_session_required
def api_platforms():
    """Return available platforms and their metadata."""
    platforms_info = []
    for name, cls in sorted(PlatformRegistry.all().items()):
        instance = cls()
        platforms_info.append({
            "name": name,
            "display_name": instance.display_name,
            "post_types": [t.value for t in instance.supported_post_types],
            "max_text_length": instance.max_text_length,
            "connected": current_user.is_connected(name),
        })
    return jsonify(platforms_info)


_ADMIN_OAUTH_KEYS = [
    ("meta_client_id", "Meta App ID", "Shared by Facebook, Instagram, WhatsApp"),
    ("meta_client_secret", "Meta App Secret", ""),
    ("linkedin_client_id", "LinkedIn Client ID", ""),
    ("linkedin_client_secret", "LinkedIn Client Secret", ""),
    ("google_client_id", "Google Client ID", "For YouTube OAuth"),
    ("google_client_secret", "Google Client Secret", ""),
    ("twitter_client_id", "Twitter/X Client ID", "OAuth 2.0 with PKCE"),
    ("twitter_client_secret", "Twitter/X Client Secret", ""),
]

_ADMIN_AI_KEYS = [
    ("ai_provider", "AI Provider", "claude or openai"),
    ("ai_claude_api_key", "Claude API Key", "From console.anthropic.com"),
    ("ai_openai_api_key", "OpenAI API Key", "From platform.openai.com"),
]

_ADMIN_BILLING_KEYS = [
    ("stripe_secret_key", "Stripe Secret Key", "sk_live_… or sk_test_…"),
    ("stripe_webhook_secret", "Stripe Webhook Secret", "whsec_… from the webhook endpoint"),
    ("stripe_price_essentials_monthly", "Stripe Price ID (Essentials Monthly)", "price_… for $6/mo"),
    ("stripe_price_essentials_yearly", "Stripe Price ID (Essentials Yearly)", "price_… for $60/yr"),
    ("stripe_price_team_monthly", "Stripe Price ID (Team Monthly)", "price_… for $12/mo"),
    ("stripe_price_team_yearly", "Stripe Price ID (Team Yearly)", "price_… for $120/yr"),
]


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 6) + value[-3:]


def _admin_only():
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "Admin access required"}), 403
    return None


@main_bp.route("/api/admin/settings", methods=["GET"])
@token_or_session_required
def api_admin_get_settings():
    block = _admin_only()
    if block is not None:
        return block
    from socialposter.web.models import AppSetting

    def section(keys):
        out = {}
        for key, label, hint in keys:
            val = AppSetting.get(key)
            out[key] = {
                "label": label,
                "hint": hint,
                "set": bool(val),
                "masked": _mask_secret(val) if key != "ai_provider" and val else (val or ""),
            }
        return out

    return jsonify({
        "oauth": section(_ADMIN_OAUTH_KEYS),
        "ai": section(_ADMIN_AI_KEYS),
        "billing": section(_ADMIN_BILLING_KEYS),
    })


@main_bp.route("/api/admin/activity", methods=["GET"])
@token_or_session_required
def api_admin_activity():
    """List recent activity log entries. Admin only."""
    block = _admin_only()
    if block is not None:
        return block
    from socialposter.utils.datetime import isoformat_or
    from socialposter.utils.pagination import paginate_query
    from socialposter.web.models import ActivityLog

    page = request.args.get("page", 1, type=int)
    action_filter = (request.args.get("action") or "").strip()
    user_filter = request.args.get("user_id", type=int)

    query = ActivityLog.query
    if action_filter:
        query = query.filter(ActivityLog.action == action_filter)
    if user_filter:
        query = query.filter(ActivityLog.user_id == user_filter)
    query = query.order_by(ActivityLog.created_at.desc())

    def _serialize(row):
        return {
            "id": row.id,
            "user_id": row.user_id,
            "user_email": row.user.email if row.user else None,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "details": row.details or {},
            "created_at": isoformat_or(row.created_at),
        }

    return jsonify(paginate_query(query, page, serializer=_serialize))


@main_bp.route("/api/admin/webhooks", methods=["GET"])
@token_or_session_required
def api_admin_webhooks():
    """List recent webhook events. Admin only."""
    block = _admin_only()
    if block is not None:
        return block
    from socialposter.utils.datetime import isoformat_or
    from socialposter.utils.pagination import paginate_query
    from socialposter.web.models import WebhookEvent

    page = request.args.get("page", 1, type=int)
    platform_filter = (request.args.get("platform") or "").strip()
    verified_filter = (request.args.get("verified") or "").strip()

    query = WebhookEvent.query
    if platform_filter:
        query = query.filter(WebhookEvent.platform == platform_filter)
    if verified_filter == "true":
        query = query.filter(WebhookEvent.verified == True)  # noqa: E712
    elif verified_filter == "false":
        query = query.filter(WebhookEvent.verified == False)  # noqa: E712
    query = query.order_by(WebhookEvent.created_at.desc())

    def _serialize(row):
        return {
            "id": row.id,
            "platform": row.platform,
            "event_type": row.event_type,
            "verified": row.verified,
            "processed": row.processed,
            "error": row.error,
            "headers": row.headers or {},
            "payload_summary": _summarize_payload(row.payload),
            "created_at": isoformat_or(row.created_at),
            "processed_at": isoformat_or(row.processed_at),
        }

    return jsonify(paginate_query(query, page, serializer=_serialize))


def _summarize_payload(payload) -> str:
    """Truncate a JSON payload to a short string for listings."""
    if payload is None:
        return ""
    import json as _json
    try:
        s = _json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        s = str(payload)
    return s[:240] + ("…" if len(s) > 240 else "")


@main_bp.route("/api/admin/settings", methods=["PUT"])
@token_or_session_required
def api_admin_update_settings():
    block = _admin_only()
    if block is not None:
        return block
    from socialposter.web.models import AppSetting
    data = request.get_json(silent=True) or {}
    allowed = (
        {k for k, _l, _h in _ADMIN_OAUTH_KEYS}
        | {k for k, _l, _h in _ADMIN_AI_KEYS}
        | {k for k, _l, _h in _ADMIN_BILLING_KEYS}
    )
    updated = []
    for key, value in data.items():
        if key not in allowed:
            continue
        value = str(value or "").strip()
        if not value:
            # Empty value -> skip (do not clobber existing)
            continue
        AppSetting.set(key, value)
        updated.append(key)
    return jsonify({"ok": True, "updated": updated})


_OAUTH_PROVIDER_KEYS = {
    "linkedin": "linkedin_client_id",
    "twitter": "twitter_client_id",
    "youtube": "google_client_id",
    "meta": "meta_client_id",
    "facebook": "meta_client_id",
    "instagram": "meta_client_id",
    "whatsapp": "meta_client_id",
}


@main_bp.route("/api/oauth/status", methods=["GET"])
@token_or_session_required
def api_oauth_status():
    """Report which platforms have admin OAuth credentials configured."""
    from socialposter.web.models import AppSetting
    out = {}
    for platform, key in _OAUTH_PROVIDER_KEYS.items():
        out[platform] = bool(AppSetting.get(key))
    return jsonify(out)


@main_bp.route("/api/connection/<platform>/disconnect", methods=["POST"])
@token_or_session_required
def api_disconnect(platform: str):
    """Remove a platform connection. Meta-linked platforms disconnect together."""
    from socialposter.web.models import PlatformConnection, db
    meta_linked = {"facebook", "instagram", "whatsapp", "meta"}
    if platform in meta_linked:
        conns = PlatformConnection.query.filter(
            PlatformConnection.user_id == current_user.id,
            PlatformConnection.platform.in_(["facebook", "instagram", "whatsapp"]),
        ).all()
    else:
        conns = PlatformConnection.query.filter_by(
            user_id=current_user.id, platform=platform
        ).all()
    if not conns:
        return jsonify({"ok": True, "removed": []})
    removed = [c.platform for c in conns]
    for conn in conns:
        db.session.delete(conn)
    db.session.commit()
    from socialposter.web.models import log_activity
    log_activity(
        current_user.id,
        "connection.disconnect",
        target_type="connection",
        target_id=platform,
        details={"removed": removed},
    )
    return jsonify({"ok": True, "removed": removed})


@main_bp.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    """Handle media file uploads. Returns the saved file path."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Sanitize and save
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

    return jsonify({
        "path": str(save_path),
        "filename": file.filename,
        "media_type": media_type,
        "size": save_path.stat().st_size,
    })


@main_bp.route("/api/post", methods=["POST"])
@login_required
def api_post():
    """Accept a post payload and publish to selected platforms."""
    data: dict[str, Any] = request.get_json(force=True)

    text = data.get("text", "")
    selected_platforms: list[str] = data.get("platforms", [])
    media_items_raw: list[dict] = data.get("media", [])
    platform_overrides: dict[str, Any] = data.get("overrides", {})
    dry_run: bool = data.get("dry_run", False)

    if not selected_platforms:
        return jsonify({"error": "No platforms selected"}), 400

    # Build media items
    media_items = []
    for m in media_items_raw:
        media_items.append(MediaItem(
            path=m["path"],
            type=m.get("media_type", "image"),
            alt_text=m.get("alt_text"),
        ))

    # Build PostFile
    defaults = DefaultContent(text=text, media=media_items)

    # Build platform overrides
    overrides_kwargs = build_platform_overrides(selected_platforms, platform_overrides)
    content = PostFile(
        defaults=defaults,
        platforms=PlatformOverrides(**overrides_kwargs),
    )

    # Resolve and publish
    platforms = _resolve_platforms(content, selected_platforms)
    if not platforms:
        return jsonify({"error": "No valid platforms resolved"}), 400

    results = []
    for platform in platforms:
        try:
            result = _publish_one(platform, content, dry_run, current_user.id)
            results.append({
                "platform": result.platform,
                "success": result.success,
                "post_id": result.post_id,
                "post_url": result.post_url,
                "error": result.error_message,
            })
            # Record post history (skip dry-run)
            if not dry_run:
                from socialposter.web.models import record_post_history
                record_post_history(
                    user_id=current_user.id,
                    platform=result.platform,
                    text=text,
                    success=result.success,
                    media=media_items_raw,
                    post_id=result.post_id,
                    post_url=result.post_url,
                    error_message=result.error_message,
                )
                if result.success and result.post_id:
                    record_published_post(
                        user_id=current_user.id,
                        team_id=get_current_team_id(current_user.id),
                        result=result,
                        text_preview=text or "",
                    )
        except Exception as e:
            results.append({
                "platform": platform.name,
                "success": False,
                "post_id": None,
                "post_url": None,
                "error": str(e),
            })

    return jsonify({"results": results})


@main_bp.route("/api/user/profile", methods=["GET"])
@token_or_session_required
def api_user_profile():
    """Return the current user's profile info."""
    return jsonify({
        "id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "timezone": current_user.timezone,
        "is_admin": current_user.is_admin,
    })


@main_bp.route("/api/user/profile", methods=["PUT"])
@token_or_session_required
def api_user_profile_update():
    """Update the current user's profile (timezone, display_name)."""
    from zoneinfo import available_timezones
    from socialposter.web.models import db

    data = request.get_json(force=True)
    if "timezone" in data:
        tz = data["timezone"]
        if tz not in available_timezones():
            return jsonify({"error": f"Invalid timezone: {tz}"}), 400
        current_user.timezone = tz
    if "display_name" in data:
        name = str(data["display_name"]).strip()
        if name:
            current_user.display_name = name
    db.session.commit()
    return jsonify({
        "id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "timezone": current_user.timezone,
    })


@main_bp.route("/offline.html")
def offline():
    """Serve the offline fallback page for the service worker."""
    return render_template("offline.html")


@main_bp.route("/manifest.json")
def manifest():
    """Serve the web app manifest for PWA support."""
    return send_from_directory(str(static_dir), "manifest.json", mimetype="application/manifest+json")


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app(test_config: dict | None = None) -> Flask:
    """Application factory – creates and configures the Flask app.

    Args:
        test_config: Optional config overrides (used by tests).
    """
    from dotenv import load_dotenv
    load_dotenv()

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
    )
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB max upload
    app.config["SECRET_KEY"] = os.environ.get(
        "SOCIALPOSTER_SECRET_KEY", "dev-secret-change-me-in-production"
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "None"
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_PERMANENT"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = 30 * 24 * 60 * 60  # 30 days

    # Database URL resolution:
    # 1. DATABASE_URL env var (Render Postgres, Heroku, etc.) — preferred for prod.
    # 2. Local SQLite at ~/.socialposter/socialposter.db — dev fallback.
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # SQLAlchemy 2.x rejects the legacy "postgres://" scheme that Render and
        # Heroku still emit. Rewrite it to the modern "postgresql://" prefix.
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]
        if not db_url.startswith(("postgresql://", "sqlite:///")):
            print(f"[socialposter] WARNING: DATABASE_URL has invalid scheme '{db_url.split('://')[0]}://' — expected 'postgresql://'. Check your Render database URL.")
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        print(f"[socialposter] Using DATABASE_URL: {db_url[:20]}...")
    else:
        db_path = Path.home() / ".socialposter" / "socialposter.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
        print(f"[socialposter] No DATABASE_URL set, using SQLite: {db_path}")

    # Apply test overrides early so they affect DB init
    if test_config:
        app.config.update(test_config)

    # Initialize extensions
    CORS(app, origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "capacitor://localhost",
        "http://localhost",
    ])

    csrf = CSRFProtect(app)

    from socialposter.web.models import db, User
    from flask_migrate import Migrate
    db.init_app(app)
    Migrate(app, db)

    login_manager = LoginManager()
    # SPA owns /login. Set the redirect target as a literal URL so Flask-Login
    # doesn't try to resolve it as a Flask route name.
    login_manager.login_view = "/login"
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from socialposter.web.auth import auth_bp
    from socialposter.web.admin import admin_bp
    from socialposter.web.oauth_routes import oauth_bp
    from socialposter.web.schedule_routes import schedule_bp
    from socialposter.web.token_auth import token_bp
    from socialposter.web.ai_routes import ai_bp
    from socialposter.web.analytics_routes import analytics_bp
    from socialposter.web.calendar_routes import calendar_bp
    from socialposter.web.team_routes import team_bp
    from socialposter.web.draft_routes import draft_bp
    from socialposter.web.inbox_routes import inbox_bp
    from socialposter.web.media_routes import media_bp
    from socialposter.web.automation_routes import automation_bp
    from socialposter.web.webhook_routes import webhook_bp
    from socialposter.web.billing_routes import billing_bp
    from socialposter.web.webinar_routes import webinar_bp
    from socialposter.web.email_routes import email_bp
    from socialposter.web.integrations_routes import integration_bp
    from socialposter.web.whatsapp_routes import whatsapp_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(token_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(draft_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(automation_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(webinar_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(integration_bp)
    app.register_blueprint(whatsapp_bp)

    # Exempt JSON-only API blueprints from CSRF; keep CSRF on form-based
    # blueprints (auth_bp, admin_bp, oauth_bp).
    for bp in (main_bp, schedule_bp, token_bp, ai_bp, analytics_bp,
               calendar_bp, team_bp, draft_bp, inbox_bp, media_bp,
               automation_bp, webhook_bp, billing_bp, webinar_bp, email_bp, integration_bp, whatsapp_bp):
        csrf.exempt(bp)

    # Surface plan-limit violations as 402 Payment Required with the
    # gate metadata, so the SPA can render an upgrade prompt.
    from socialposter.core.plans import PlanLimitExceeded

    @app.errorhandler(PlanLimitExceeded)
    def _handle_plan_limit(exc: PlanLimitExceeded):
        return jsonify(exc.to_dict()), 402

    # Create tables and run auto-migrations.
    # Wrapped in a broad try/except so that database issues never prevent
    # the SPA from being registered (the app must at least serve the UI).
    try:
        with app.app_context():
            try:
                db.create_all()
            except Exception as exc:
                app.logger.warning("db.create_all() skipped: %s", exc)

            # Auto-migration: add missing columns to existing tables
            import sqlalchemy
            with db.engine.connect() as conn:
                inspector = sqlalchemy.inspect(db.engine)
                if "users" in inspector.get_table_names():
                    cols = [c["name"] for c in inspector.get_columns("users")]
                    if "timezone" not in cols:
                        conn.execute(sqlalchemy.text(
                            "ALTER TABLE users ADD COLUMN timezone VARCHAR(50) NOT NULL DEFAULT 'UTC'"
                        ))
                        conn.commit()

            # Auto-migration: ensure admin users have a default team
            from socialposter.web.models import Team, TeamMember
            admin_users = User.query.filter_by(is_admin=True).all()
            for admin in admin_users:
                if not TeamMember.query.filter_by(user_id=admin.id).first():
                    existing_team = Team.query.first()
                    if not existing_team:
                        existing_team = Team(
                            name="Default Team",
                            slug="default-team",
                            created_by=admin.id,
                        )
                        db.session.add(existing_team)
                        db.session.flush()
                    db.session.add(TeamMember(
                        team_id=existing_team.id,
                        user_id=admin.id,
                        role="admin",
                    ))
            db.session.commit()
    except Exception as exc:
        print(f"[socialposter] DB init error (non-fatal): {exc}")

    # Start background scheduler (avoid double-start in Flask reloader, and
    # skip entirely in tests / worker processes).
    try:
        if (
            not app.config.get("TESTING")
            and not os.environ.get("SOCIALPOSTER_SKIP_SCHEDULER")
            and (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true")
        ):
            from socialposter.core.scheduler import init_scheduler
            init_scheduler(app)
    except Exception as exc:
        print(f"[socialposter] Scheduler init error (non-fatal): {exc}")

    _register_spa(app)

    return app


# ---------------------------------------------------------------------------
# SPA serving
# ---------------------------------------------------------------------------

def _register_spa(app: Flask) -> None:
    """Serve the built React SPA (frontend/dist) for any non-API path.

    Looks for the build at several candidate locations. If absent (eg. local
    dev where the SPA is served separately by Vite), this is a no-op and
    Flask returns 404 for unknown paths as usual.
    """
    me = Path(__file__).resolve()
    candidates = [
        me.parent / "static" / "spa",              # package data or post-install copy
        Path.cwd() / "frontend" / "dist",          # local dev or Render working dir
        me.parents[3] / "frontend" / "dist",       # editable install: src/socialposter/web/app.py
        me.parents[2] / "frontend" / "dist",       # possible layout variant
        Path("/opt/render/project/src/frontend/dist"),
        Path("/var/data/frontend/dist"),             # Render persistent disk (runtime only)
    ]
    print(f"[socialposter] SPA candidates: {[str(c) + ' exists=' + str((c / 'index.html').exists()) for c in candidates]}")
    spa_dir = next((p for p in candidates if (p / "index.html").exists()), None)
    if spa_dir is None:
        print("[socialposter] SPA build NOT found — Flask will return 404 for non-API paths.")
        return

    print(f"[socialposter] Serving SPA from {spa_dir}")
    index_html = (spa_dir / "index.html").read_text(encoding="utf-8")

    # Reserved prefixes that the SPA must NOT shadow.
    api_prefixes = ("api/", "oauth/", "uploads/", "static/", "admin/api")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa_catch_all(path: str):
        # Don't shadow API / OAuth / file routes — let Flask 404 if they
        # reach here (they shouldn't, since real routes match first).
        if any(path.startswith(p) for p in api_prefixes):
            return jsonify({"error": "Not found"}), 404

        # If the request is for a real file in the SPA build, serve it.
        if path:
            target = (spa_dir / path).resolve()
            if (
                target.is_file()
                and spa_dir.resolve() in target.parents
            ):
                return send_from_directory(spa_dir, path)

        # Otherwise hand back index.html so React Router takes over.
        return index_html, 200, {"Content-Type": "text/html; charset=utf-8"}


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = True):
    """Launch the Flask development server."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)
