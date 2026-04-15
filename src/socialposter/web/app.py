"""Flask web UI for SocialPoster – compose & publish posts via the browser."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy
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

UPLOAD_DIR = Path.home() / ".socialposter" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Main blueprint – existing routes live here
# ---------------------------------------------------------------------------

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    """Serve the main UI."""
    return render_template("index.html")


@main_bp.route("/connections")
@login_required
def connections():
    """Show platform connection status."""
    from socialposter.utils.datetime import isoformat_or

    platforms_info = []
    for name, cls in sorted(PlatformRegistry.all().items()):
        instance = cls()
        conn = current_user.get_connection(name)
        info = {
            "name": name,
            "display_name": instance.display_name,
            "connected": conn is not None,
            "extra_data": conn.extra_data if conn else {},
        }
        if conn:
            info["connected_at"] = isoformat_or(conn.connected_at)
            info["expires_at"] = isoformat_or(conn.token_expires_at)
            info["is_expired"] = conn.is_token_expired
            info["account_name"] = (conn.extra_data or {}).get("account_name", "")
        platforms_info.append(info)
    return render_template("connections.html", platforms=platforms_info)


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

    # SQLite database in the config dir
    db_path = Path.home() / ".socialposter" / "socialposter.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

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
    login_manager.login_view = "auth.login"
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
    from socialposter.web.user_ai_routes import user_ai_bp
    from socialposter.web.webhook_routes import webhook_bp
    from socialposter.web.competitor_routes import competitor_bp

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
    app.register_blueprint(user_ai_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(competitor_bp)

    # Exempt JSON-only API blueprints from CSRF; keep CSRF on form-based
    # blueprints (auth_bp, admin_bp, oauth_bp).
    for bp in (main_bp, schedule_bp, token_bp, ai_bp, analytics_bp,
               calendar_bp, team_bp, draft_bp, inbox_bp, media_bp,
               automation_bp, user_ai_bp, webhook_bp, competitor_bp):
        csrf.exempt(bp)

    # Create tables
    with app.app_context():
        try:
            db.create_all()
        except sqlalchemy.exc.OperationalError as exc:
            message = str(exc).lower()
            if "already exists" in message or "table users already exists" in message:
                logging.warning("Database table already exists during startup; continuing.")
            else:
                raise

        # Auto-migration: add missing columns to existing tables
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

    # Start background scheduler (avoid double-start in Flask reloader)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from socialposter.core.scheduler import init_scheduler
        init_scheduler(app)

    return app


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = True):
    """Launch the Flask development server."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)
