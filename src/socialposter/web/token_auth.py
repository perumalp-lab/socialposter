"""JWT token authentication for mobile clients (Capacitor)."""

from __future__ import annotations

import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_user
from werkzeug.security import check_password_hash

from socialposter.web.models import User, db

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
                    login_user(user, remember=False)
                    return f(*args, **kwargs)

        return jsonify({"error": "Authentication required"}), 401

    return decorated
