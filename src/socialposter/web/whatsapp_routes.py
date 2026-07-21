from __future__ import annotations

import requests
from flask import Blueprint, jsonify, request
from flask_login import current_user

from socialposter.web.models import PlatformConnection, WhatsAppMessage, db

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/api/whatsapp")


def _get_conn() -> PlatformConnection | None:
    return PlatformConnection.query.filter_by(
        user_id=current_user.id, platform="whatsapp"
    ).first()


def _settings_json(conn: PlatformConnection | None) -> dict:
    if not conn:
        return {
            "phone_number_id": "",
            "business_account_id": "",
            "has_access_token": False,
            "webhook_verify_token": "",
        }
    extra = conn.extra_data or {}
    return {
        "phone_number_id": extra.get("phone_number_id", ""),
        "business_account_id": extra.get("business_account_id", ""),
        "has_access_token": bool(conn.access_token),
        "webhook_verify_token": extra.get("webhook_verify_token", ""),
    }


@whatsapp_bp.route("/settings", methods=["GET"])
def get_settings():
    return jsonify(_settings_json(_get_conn()))


@whatsapp_bp.route("/settings", methods=["PUT"])
def update_settings():
    conn = _get_conn()
    if not conn:
        conn = PlatformConnection(
            user_id=current_user.id,
            platform="whatsapp",
            access_token="",
            extra_data={},
        )
        db.session.add(conn)

    data = request.get_json(force=True)
    extra = dict(conn.extra_data or {})

    for field in ("phone_number_id", "business_account_id", "webhook_verify_token"):
        if field in data:
            extra[field] = data[field]

    if "access_token" in data:
        conn.access_token = data["access_token"]

    conn.extra_data = extra
    db.session.commit()
    return jsonify(_settings_json(conn))


@whatsapp_bp.route("/test", methods=["POST"])
def send_test_message():
    conn = _get_conn()
    extra = (conn.extra_data or {}) if conn else {}
    phone_id = extra.get("phone_number_id", "") if conn else ""
    token = conn.access_token if conn else ""

    if not phone_id or not token:
        return jsonify({"error": "WhatsApp not configured"}), 400

    data = request.get_json(force=True)
    to = data.get("to", "").strip()
    body = data.get("body", "Test message from Kryptams").strip()
    if not to:
        return jsonify({"error": "Recipient phone number is required"}), 400

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        result = resp.json()
        if resp.ok:
            return jsonify({"ok": True, "message_id": result.get("messages", [{}])[0].get("id")})
        return jsonify({"ok": False, "error": result.get("error", {}).get("message", str(result))})
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": str(e)})


@whatsapp_bp.route("/messages", methods=["GET"])
def list_messages():
    msgs = WhatsAppMessage.query.filter_by(user_id=current_user.id).order_by(WhatsAppMessage.created_at.desc()).all()
    return jsonify([
        {
            "id": m.id,
            "name": m.name,
            "template_name": m.template_name,
            "body": m.body,
            "language": m.language,
            "header_type": m.header_type,
            "header_value": m.header_value,
            "footer": m.footer,
            "created_at": m.created_at.isoformat() + "Z" if m.created_at else None,
            "updated_at": m.updated_at.isoformat() + "Z" if m.updated_at else None,
        }
        for m in msgs
    ])


@whatsapp_bp.route("/messages", methods=["POST"])
def create_message():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    m = WhatsAppMessage(
        user_id=current_user.id,
        name=name,
        template_name=data.get("template_name", ""),
        body=data.get("body", ""),
        language=data.get("language", "en"),
        header_type=data.get("header_type", "none"),
        header_value=data.get("header_value", ""),
        footer=data.get("footer", ""),
    )
    db.session.add(m)
    db.session.commit()
    return jsonify({"id": m.id, "name": m.name}), 201


@whatsapp_bp.route("/messages/<int:msg_id>", methods=["PUT"])
def update_message(msg_id: int):
    m = WhatsAppMessage.query.filter_by(id=msg_id, user_id=current_user.id).first()
    if not m:
        return jsonify({"error": "Message not found"}), 404
    data = request.get_json(force=True)
    for field in ("name", "template_name", "body", "language", "header_type", "header_value", "footer"):
        if field in data:
            setattr(m, field, data[field])
    db.session.commit()
    return jsonify({"ok": True})


@whatsapp_bp.route("/messages/<int:msg_id>", methods=["DELETE"])
def delete_message(msg_id: int):
    m = WhatsAppMessage.query.filter_by(id=msg_id, user_id=current_user.id).first()
    if not m:
        return jsonify({"error": "Message not found"}), 404
    db.session.delete(m)
    db.session.commit()
    return jsonify({"ok": True})


@whatsapp_bp.route("/messages/<int:msg_id>/send", methods=["POST"])
def send_template_message(msg_id: int):
    m = WhatsAppMessage.query.filter_by(id=msg_id, user_id=current_user.id).first()
    if not m:
        return jsonify({"error": "Message not found"}), 404

    conn = _get_conn()
    extra = (conn.extra_data or {}) if conn else {}
    phone_id = extra.get("phone_number_id", "") if conn else ""
    token = conn.access_token if conn else ""

    if not phone_id or not token:
        return jsonify({"error": "WhatsApp not configured"}), 400

    data = request.get_json(force=True)
    to = data.get("to", "").strip()
    if not to:
        return jsonify({"error": "Recipient phone number is required"}), 400

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": m.body},
    }
    if m.template_name:
        components = [{"type": "body", "parameters": [{"type": "text", "text": m.body}]}]
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": m.template_name,
                "language": {"code": m.language},
                "components": components,
            },
        }
        if m.header_type == "image" and m.header_value:
            payload["template"]["components"].insert(0, {
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": m.header_value}}],
            })

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        result = resp.json()
        if resp.ok:
            return jsonify({"ok": True, "message_id": result.get("messages", [{}])[0].get("id")})
        return jsonify({"ok": False, "error": result.get("error", {}).get("message", str(result))})
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": str(e)})
