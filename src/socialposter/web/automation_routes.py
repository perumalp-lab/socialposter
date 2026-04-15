"""Automation rules blueprint – CRUD for rules, toggle, logs."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from socialposter.utils.datetime import isoformat_or
from socialposter.web.models import AutomationRule, AutomationLog, db
from socialposter.web.token_auth import token_or_session_required

automation_bp = Blueprint("automation", __name__)


@automation_bp.route("/automation")
@login_required
def automation_page():
    """Serve the automation rules UI."""
    return render_template("automation.html")


@automation_bp.route("/api/automation/rules", methods=["GET"])
@token_or_session_required
def api_rules_list():
    """List all automation rules for the current user."""
    rules = AutomationRule.query.filter_by(user_id=current_user.id).order_by(
        AutomationRule.created_at.desc()
    ).all()

    return jsonify([
        {
            "id": r.id,
            "name": r.name,
            "trigger_type": r.trigger_type,
            "conditions": r.conditions,
            "actions": r.actions,
            "enabled": r.enabled,
            "last_triggered_at": isoformat_or(r.last_triggered_at),
            "trigger_count": r.trigger_count,
            "created_at": isoformat_or(r.created_at),
        }
        for r in rules
    ])


@automation_bp.route("/api/automation/rules", methods=["POST"])
@token_or_session_required
def api_rules_create():
    """Create a new automation rule."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    trigger_type = (data.get("trigger_type") or "").strip()
    conditions = data.get("conditions", {})
    actions = data.get("actions", [])

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if trigger_type not in ("engagement_threshold", "no_post_interval"):
        return jsonify({"error": "Invalid trigger type"}), 400
    if not actions:
        return jsonify({"error": "At least one action is required"}), 400

    # Validate actions
    valid_action_types = {"repost", "ai_generate", "notify", "webhook"}
    for a in actions:
        if a.get("type") not in valid_action_types:
            return jsonify({"error": f"Invalid action type: {a.get('type')}"}), 400

    rule = AutomationRule(
        user_id=current_user.id,
        name=name,
        trigger_type=trigger_type,
        conditions=conditions,
        actions=actions,
    )
    db.session.add(rule)
    db.session.commit()

    return jsonify({"ok": True, "id": rule.id})


@automation_bp.route("/api/automation/rules/<int:rule_id>", methods=["PUT"])
@token_or_session_required
def api_rules_update(rule_id: int):
    """Update an existing automation rule."""
    rule = AutomationRule.query.filter_by(
        id=rule_id, user_id=current_user.id
    ).first()
    if not rule:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        rule.name = str(data["name"]).strip()
    if "trigger_type" in data:
        if data["trigger_type"] not in ("engagement_threshold", "no_post_interval"):
            return jsonify({"error": "Invalid trigger type"}), 400
        rule.trigger_type = data["trigger_type"]
    if "conditions" in data:
        rule.conditions = data["conditions"]
    if "actions" in data:
        rule.actions = data["actions"]

    db.session.commit()
    return jsonify({"ok": True})


@automation_bp.route("/api/automation/rules/<int:rule_id>", methods=["DELETE"])
@token_or_session_required
def api_rules_delete(rule_id: int):
    """Delete an automation rule."""
    rule = AutomationRule.query.filter_by(
        id=rule_id, user_id=current_user.id
    ).first()
    if not rule:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(rule)
    db.session.commit()
    return jsonify({"ok": True})


@automation_bp.route("/api/automation/rules/<int:rule_id>/toggle", methods=["POST"])
@token_or_session_required
def api_rules_toggle(rule_id: int):
    """Toggle a rule's enabled state."""
    rule = AutomationRule.query.filter_by(
        id=rule_id, user_id=current_user.id
    ).first()
    if not rule:
        return jsonify({"error": "Not found"}), 404

    rule.enabled = not rule.enabled
    db.session.commit()
    return jsonify({"ok": True, "enabled": rule.enabled})


@automation_bp.route("/api/automation/rules/<int:rule_id>/logs", methods=["GET"])
@token_or_session_required
def api_rules_logs(rule_id: int):
    """Get execution logs for a rule."""
    rule = AutomationRule.query.filter_by(
        id=rule_id, user_id=current_user.id
    ).first()
    if not rule:
        return jsonify({"error": "Not found"}), 404

    logs = AutomationLog.query.filter_by(rule_id=rule_id).order_by(
        AutomationLog.triggered_at.desc()
    ).limit(50).all()

    return jsonify([
        {
            "id": l.id,
            "triggered_at": isoformat_or(l.triggered_at),
            "conditions_met": l.conditions_met,
            "actions_taken": l.actions_taken,
            "success": l.success,
            "error_message": l.error_message,
        }
        for l in logs
    ])
