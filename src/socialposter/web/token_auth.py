"""JWT token authentication for mobile clients (Capacitor)."""

from __future__ import annotations

import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash

from socialposter.web.models import Team, TeamMember, User, db

token_bp = Blueprint("token_auth", __name__, url_prefix="/api/auth")

# Token expiry: 30 days
TOKEN_EXPIRY_DAYS = 30


def _create_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


@token_bp.route("/login", methods=["POST"])
def token_login():
    """Authenticate with email/password and return a JWT."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = _create_token(user.id)
    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
        },
    })


@token_bp.route("/refresh", methods=["POST"])
def token_refresh():
    """Refresh a valid JWT and return a new one."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Bearer token required"}), 401

    token = auth_header[7:]
    payload = _decode_token(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401

    user = db.session.get(User, payload["sub"])
    if not user:
        return jsonify({"error": "User not found"}), 401

    new_token = _create_token(user.id)
    return jsonify({"token": new_token})


@token_bp.route("/session-login", methods=["POST"])
def session_login():
    """Authenticate with email/password and set the Flask-Login session cookie."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    login_user(user)
    from socialposter.web.models import log_activity
    log_activity(
        user.id,
        "auth.login",
        target_type="user",
        target_id=user.id,
        details={"email": user.email},
    )
    return jsonify({"user": _user_dict(user)})


@token_bp.route("/session-signup", methods=["POST"])
def session_signup():
    """Create a new account and set the Flask-Login session cookie."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip()
    tz = (data.get("timezone") or "UTC").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists"}), 409

    is_first = User.query.count() == 0
    name = display_name or email.split("@")[0]
    user = User(
        email=email,
        display_name=name,
        is_admin=is_first,
        timezone=tz,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    # Every SPA signup gets a personal workspace they own as admin, so the
    # team-gated APIs (/api/drafts, /api/inbox/*, etc.) work immediately.
    slug_base = (name.lower().replace(" ", "-") or f"user-{user.id}")
    slug = slug_base
    suffix = 2
    while Team.query.filter_by(slug=slug).first() is not None:
        slug = f"{slug_base}-{suffix}"
        suffix += 1
    team = Team(name=f"{name}'s workspace", slug=slug, created_by=user.id)
    db.session.add(team)
    db.session.flush()
    db.session.add(TeamMember(team_id=team.id, user_id=user.id, role="admin"))

    db.session.commit()
    login_user(user)
    return jsonify({"user": _user_dict(user)}), 201


@token_bp.route("/me", methods=["GET"])
def me():
    """Return the currently authenticated user, or 401."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({"user": _user_dict(current_user)})


@token_bp.route("/profile", methods=["PUT"])
def update_profile():
    """Update the current user's display name and timezone."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    changed = False
    if "display_name" in data:
        name = (data["display_name"] or "").strip()
        if not name:
            return jsonify({"error": "Display name cannot be empty"}), 400
        current_user.display_name = name
        changed = True
    if "timezone" in data:
        tz = (data["timezone"] or "").strip()
        if tz:
            current_user.timezone = tz
            changed = True
    if changed:
        db.session.commit()
    return jsonify({"ok": True, "user": _user_dict(current_user)})


@token_bp.route("/password", methods=["POST"])
def change_password():
    """Change the current user's password. Requires the current password."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new_password = data.get("new_password") or ""
    if not current or not new_password:
        return jsonify({"error": "Current and new password are required"}), 400
    if not check_password_hash(current_user.password_hash, current):
        return jsonify({"error": "Current password is incorrect"}), 401
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({"ok": True})


@token_bp.route("/session-logout", methods=["POST"])
def session_logout():
    logout_user()
    return jsonify({"ok": True})


def _user_dict(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": bool(getattr(user, "is_admin", False)),
    }


def token_or_session_required(f):
    """Decorator: accepts either Flask-Login session OR Bearer JWT token."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # Already authenticated via session?
        if current_user.is_authenticated:
            return f(*args, **kwargs)

        # Try Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = _decode_token(token)
            if payload:
                user = db.session.get(User, payload["sub"])
                if user:
                    return f(*args, **kwargs)

        return jsonify({"error": "Authentication required"}), 401

    return decorated
