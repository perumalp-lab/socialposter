"""Auth blueprint – login, signup, logout."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from socialposter.web.models import User, Team, TeamMember, db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.index"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        tz = request.form.get("timezone", "UTC").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            # First user is auto-admin
            is_first = User.query.count() == 0

            user = User(
                email=email,
                display_name=display_name or email.split("@")[0],
                is_admin=is_first,
                timezone=tz or "UTC",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get user.id before creating team

            # Auto-create a default team for the first (admin) user
            if is_first:
                team = Team(
                    name="Default Team",
                    slug="default-team",
                    created_by=user.id,
                )
                db.session.add(team)
                db.session.flush()
                db.session.add(TeamMember(
                    team_id=team.id,
                    user_id=user.id,
                    role="admin",
                ))

            db.session.commit()

            login_user(user)
            if is_first:
                flash("Welcome! You are the admin. Configure OAuth settings under Admin.", "success")
                return redirect(url_for("admin.settings"))
            return redirect(url_for("main.index"))

    return render_template("signup.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
