"""Auth blueprint – login, signup, logout."""

from __future__ import annotations

import logging
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from socialposter.web.models import User, Team, TeamMember, db

log = logging.getLogger("socialposter")

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        log.info("Login attempt for email: %s", email)
        
        # Ensure fresh database session
        db.session.expunge_all()
        user = User.query.filter_by(email=email).first()
        
        if not user:
            log.warning("User not found: %s", email)
            flash("Invalid email or password.", "error")
            return render_template("login.html")
        
        log.info("User found: %s (id=%s, has_password_hash=%s)", email, user.id, bool(user.password_hash))
        
        # Debug password verification
        try:
            is_correct = user.check_password(password)
            log.info("Password verification result: %s (hash_length=%d)", is_correct, len(user.password_hash) if user.password_hash else 0)
        except Exception as e:
            log.error("Error during password check: %s", e)
            flash("An error occurred during login. Please try again.", "error")
            return render_template("login.html")
        
        if not is_correct:
            log.warning("Incorrect password for user: %s", email)
            flash("Invalid email or password.", "error")
            return render_template("login.html")
        
        log.info("User authenticated successfully: %s (id=%s)", email, user.id)
        remember = request.form.get("remember", False)
        login_user(user, remember=remember)
        log.info("User logged in: %s", email)
        
        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.index"))
    
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
            try:
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
                log.info("User created: %s (id=%s, is_admin=%s)", email, user.id, is_first)

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
                    log.info("Default team created for admin user: %s", email)

                db.session.commit()
                log.info("User registration completed and committed to database: %s", email)
                log.info("Password hash after commit: length=%d", len(user.password_hash) if user.password_hash else 0)
                
                # Refresh user from database to ensure it's in current session
                db.session.refresh(user)
                log.info("User refreshed from database: email=%s, pwd_hash_len=%d", email, len(user.password_hash) if user.password_hash else 0)
                login_user(user)
                if is_first:
                    flash("Welcome! You are the admin. Configure OAuth settings under Admin.", "success")
                    return redirect(url_for("admin.settings"))
                flash("Account created successfully! You are now logged in.", "success")
                return redirect(url_for("main.index"))
            except Exception as e:
                db.session.rollback()
                log.exception("Error during user registration: %s", e)
                flash("An error occurred during registration. Please try again.", "error")

    return render_template("signup.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
