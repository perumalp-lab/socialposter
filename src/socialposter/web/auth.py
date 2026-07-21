"""Auth blueprint – logout endpoint only.

The SPA replaces the old form-based login/signup; it uses the JSON endpoints
in token_auth.py (/api/auth/session-login, /api/auth/session-signup,
/api/auth/session-logout). Flask-Login's login_view is set to the literal
URL "/login" in app.py so unauthenticated redirects land on the SPA's
LoginPage (served by the catch-all in app.py).
"""

from __future__ import annotations

from flask import Blueprint
from flask_login import logout_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    return ("", 204)
