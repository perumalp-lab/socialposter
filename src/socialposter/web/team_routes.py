"""Team management blueprint – create teams, invite users, manage roles."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, render_template, request
from flask_login import current_user, login_required

from socialposter.web.models import Team, TeamMember, User, db
from socialposter.web.permissions import team_required, role_required

team_bp = Blueprint("team", __name__)


# /team Jinja page removed — React SPA owns it.


@team_bp.route("/api/team", methods=["GET"])
@login_required
def api_team_get():
    """Return the current user's team plus members."""
    membership = TeamMember.query.filter_by(user_id=current_user.id).first()
    if not membership:
        return jsonify({"team": None, "members": [], "role": None})

    team = membership.team
    members = TeamMember.query.filter_by(team_id=team.id).all()
    return jsonify({
        "team": {
            "id": team.id,
            "name": team.name,
            "slug": team.slug,
            "created_at": team.created_at.isoformat() if team.created_at else None,
        },
        "role": membership.role,
        "members": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "email": m.user.email if m.user else "",
                "display_name": m.user.display_name if m.user else "",
                "is_admin": bool(getattr(m.user, "is_admin", False)) if m.user else False,
                "role": m.role,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            for m in members
        ],
    })


@team_bp.route("/team/create", methods=["POST"])
@team_bp.route("/api/team", methods=["POST"])
@login_required
def create_team():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Team name is required"}), 400

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if Team.query.filter_by(slug=slug).first():
        return jsonify({"error": "A team with that name already exists"}), 409

    team = Team(name=name, slug=slug, created_by=current_user.id)
    db.session.add(team)
    db.session.flush()

    member = TeamMember(team_id=team.id, user_id=current_user.id, role="admin")
    db.session.add(member)
    db.session.commit()

    return jsonify({"ok": True, "team_id": team.id, "slug": team.slug})


@team_bp.route("/team/invite", methods=["POST"])
@team_bp.route("/api/team/invite", methods=["POST"])
@login_required
@team_required
@role_required("admin")
def invite_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    role = data.get("role", "editor")
    if role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Invalid role"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "No user with that email"}), 404

    existing = TeamMember.query.filter_by(team_id=g.team.id, user_id=user.id).first()
    if existing:
        return jsonify({"error": "User is already a team member"}), 409

    member = TeamMember(team_id=g.team.id, user_id=user.id, role=role)
    db.session.add(member)
    db.session.commit()

    return jsonify({"ok": True, "user_id": user.id, "display_name": user.display_name})


@team_bp.route("/team/members/<int:member_id>/role", methods=["POST"])
@team_bp.route("/api/team/members/<int:member_id>/role", methods=["POST"])
@login_required
@team_required
@role_required("admin")
def change_role(member_id: int):
    member = TeamMember.query.filter_by(id=member_id, team_id=g.team.id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404

    data = request.get_json(silent=True) or {}
    new_role = data.get("role", "")
    if new_role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Invalid role"}), 400

    member.role = new_role
    db.session.commit()
    return jsonify({"ok": True})


@team_bp.route("/team/members/<int:user_id>/site-admin", methods=["POST"])
@team_bp.route("/api/team/members/<int:user_id>/site-admin", methods=["POST"])
@login_required
@team_required
@role_required("admin")
def toggle_site_admin(user_id: int):
    """Toggle is_admin flag for a user. Only site admins can do this."""
    if not current_user.is_admin:
        return jsonify({"error": "Only site admins can change this"}), 403
    if user_id == current_user.id:
        return jsonify({"error": "Cannot change your own admin status"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    user.is_admin = bool(data.get("is_admin", False))
    db.session.commit()
    return jsonify({"ok": True, "is_admin": user.is_admin})


@team_bp.route("/team/members/<int:member_id>/remove", methods=["POST"])
@team_bp.route("/api/team/members/<int:member_id>/remove", methods=["POST"])
@login_required
@team_required
@role_required("admin")
def remove_member(member_id: int):
    member = TeamMember.query.filter_by(id=member_id, team_id=g.team.id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404
    if member.user_id == current_user.id:
        return jsonify({"error": "Cannot remove yourself"}), 400

    db.session.delete(member)
    db.session.commit()
    return jsonify({"ok": True})
