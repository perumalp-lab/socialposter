"""Webhook management API + inbound webhook receiver."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from socialposter.core.webhook_dispatcher import WEBHOOK_EVENTS
from socialposter.utils.datetime import isoformat_or
from socialposter.web.models import (
    WebhookEndpoint, WebhookInboundToken, WebhookDeliveryLog, db,
)
from socialposter.web.token_auth import token_or_session_required

webhook_bp = Blueprint("webhooks", __name__)


# ---------------------------------------------------------------------------
# UI page
# ---------------------------------------------------------------------------

@webhook_bp.route("/webhooks")
@login_required
def webhooks_page():
    return render_template("webhooks.html")


# ---------------------------------------------------------------------------
# Outbound endpoint management
# ---------------------------------------------------------------------------

@webhook_bp.route("/api/webhooks", methods=["GET"])
@token_or_session_required
def list_endpoints():
    endpoints = WebhookEndpoint.query.filter_by(user_id=current_user.id).order_by(
        WebhookEndpoint.created_at.desc()
    ).all()
    return jsonify([
        {
            "id": ep.id,
            "name": ep.name,
            "url": ep.url,
            "events": ep.events,
            "is_active": ep.is_active,
            "created_at": isoformat_or(ep.created_at),
        }
        for ep in endpoints
    ])


@webhook_bp.route("/api/webhooks", methods=["POST"])
@token_or_session_required
def create_endpoint():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    events = data.get("events") or []
    secret = (data.get("secret") or "").strip() or secrets.token_hex(32)

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Validate events
    for e in events:
        if e not in WEBHOOK_EVENTS:
            return jsonify({"error": f"Invalid event: {e}"}), 400

    ep = WebhookEndpoint(
        user_id=current_user.id,
        name=name,
        url=url,
        secret=secret,
        events=events,
    )
    db.session.add(ep)
    db.session.commit()
    return jsonify({"ok": True, "id": ep.id, "secret": secret})


@webhook_bp.route("/api/webhooks/<int:ep_id>", methods=["PUT"])
@token_or_session_required
def update_endpoint(ep_id: int):
    ep = WebhookEndpoint.query.filter_by(id=ep_id, user_id=current_user.id).first()
    if not ep:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        ep.name = str(data["name"]).strip()
    if "url" in data:
        ep.url = str(data["url"]).strip()
    if "events" in data:
        ep.events = data["events"]
    if "is_active" in data:
        ep.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify({"ok": True})


@webhook_bp.route("/api/webhooks/<int:ep_id>", methods=["DELETE"])
@token_or_session_required
def delete_endpoint(ep_id: int):
    ep = WebhookEndpoint.query.filter_by(id=ep_id, user_id=current_user.id).first()
    if not ep:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(ep)
    db.session.commit()
    return jsonify({"ok": True})


@webhook_bp.route("/api/webhooks/<int:ep_id>/test", methods=["POST"])
@token_or_session_required
def test_endpoint(ep_id: int):
    ep = WebhookEndpoint.query.filter_by(id=ep_id, user_id=current_user.id).first()
    if not ep:
        return jsonify({"error": "Not found"}), 404

    from socialposter.core.webhook_dispatcher import _deliver
    _deliver(ep, "test.ping", {"message": "Test webhook from SocialPoster"}, db)
    return jsonify({"ok": True})


@webhook_bp.route("/api/webhooks/<int:ep_id>/logs", methods=["GET"])
@token_or_session_required
def endpoint_logs(ep_id: int):
    ep = WebhookEndpoint.query.filter_by(id=ep_id, user_id=current_user.id).first()
    if not ep:
        return jsonify({"error": "Not found"}), 404

    logs = WebhookDeliveryLog.query.filter_by(endpoint_id=ep_id).order_by(
        WebhookDeliveryLog.created_at.desc()
    ).limit(50).all()

    return jsonify([
        {
            "id": l.id,
            "event": l.event,
            "response_status": l.response_status,
            "success": l.success,
            "error_message": l.error_message,
            "created_at": isoformat_or(l.created_at),
        }
        for l in logs
    ])


# ---------------------------------------------------------------------------
# Inbound tokens
# ---------------------------------------------------------------------------

@webhook_bp.route("/api/webhooks/inbound-tokens", methods=["GET"])
@token_or_session_required
def list_inbound_tokens():
    tokens = WebhookInboundToken.query.filter_by(user_id=current_user.id).order_by(
        WebhookInboundToken.created_at.desc()
    ).all()
    return jsonify([
        {
            "id": t.id,
            "name": t.name,
            "token": t.token,
            "is_active": t.is_active,
            "last_used_at": isoformat_or(t.last_used_at),
            "created_at": isoformat_or(t.created_at),
        }
        for t in tokens
    ])


@webhook_bp.route("/api/webhooks/inbound-tokens", methods=["POST"])
@token_or_session_required
def create_inbound_token():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip() or "Unnamed Token"

    token = secrets.token_hex(32)
    t = WebhookInboundToken(
        user_id=current_user.id,
        token=token,
        name=name,
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({"ok": True, "id": t.id, "token": token})


@webhook_bp.route("/api/webhooks/inbound-tokens/<int:token_id>", methods=["DELETE"])
@token_or_session_required
def delete_inbound_token(token_id: int):
    t = WebhookInboundToken.query.filter_by(
        id=token_id, user_id=current_user.id
    ).first()
    if not t:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Inbound receiver (token-based auth, no session/JWT)
# ---------------------------------------------------------------------------

@webhook_bp.route("/api/webhooks/incoming/<token>", methods=["POST"])
def incoming_webhook(token: str):
    """Handle inbound webhook actions — authenticated by URL token."""
    tok = WebhookInboundToken.query.filter_by(token=token, is_active=True).first()
    if not tok:
        return jsonify({"error": "Invalid or inactive token"}), 401

    tok.last_used_at = datetime.now(timezone.utc)
    db.session.commit()

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()

    if action == "create_post":
        return _handle_create_post(tok.user_id, data)
    elif action == "ai_generate":
        return _handle_ai_generate(tok.user_id, data)
    elif action == "trigger_automation":
        return _handle_trigger_automation(tok.user_id, data)
    else:
        return jsonify({"error": f"Unknown action: {action}"}), 400


def _handle_create_post(user_id: int, data: dict):
    """Queue a post for publishing via inbound webhook."""
    from socialposter.core.content import DefaultContent, PlatformOverrides, PostFile
    from socialposter.core.publisher import _publish_one, _resolve_platforms
    from socialposter.web.models import record_post_history

    text = (data.get("text") or "").strip()
    platforms = data.get("platforms") or []

    if not text:
        return jsonify({"error": "text is required"}), 400
    if not platforms:
        return jsonify({"error": "platforms is required"}), 400

    content = PostFile(
        defaults=DefaultContent(text=text),
        platforms=PlatformOverrides(),
    )
    resolved = _resolve_platforms(content, platforms)
    results = []
    for platform in resolved:
        try:
            result = _publish_one(platform, content, dry_run=False, user_id=user_id)
            results.append({
                "platform": result.platform,
                "success": result.success,
                "post_id": result.post_id,
                "error": result.error_message,
            })
            record_post_history(
                user_id=user_id,
                platform=result.platform,
                text=text,
                success=result.success,
                post_id=result.post_id,
                post_url=result.post_url,
                error_message=result.error_message,
            )
        except Exception as e:
            results.append({"platform": platform.name, "success": False, "error": str(e)})

    return jsonify({"results": results})


def _handle_ai_generate(user_id: int, data: dict):
    """Generate content via AI and return it."""
    from socialposter.core.ai_service import generate_content

    topic = (data.get("topic") or "").strip()
    platforms = data.get("platforms") or []

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    try:
        text = generate_content(topic, platforms, user_id=user_id)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


def _handle_trigger_automation(user_id: int, data: dict):
    """Manually trigger a specific automation rule."""
    from socialposter.web.models import AutomationRule
    from socialposter.core.automation_engine import _execute_actions, _check_conditions

    rule_id = data.get("rule_id")
    if not rule_id:
        return jsonify({"error": "rule_id is required"}), 400

    rule = AutomationRule.query.filter_by(id=rule_id, user_id=user_id).first()
    if not rule:
        return jsonify({"error": "Rule not found"}), 404

    from flask import current_app
    results = _execute_actions(rule, current_app._get_current_object())
    return jsonify({"results": results})
