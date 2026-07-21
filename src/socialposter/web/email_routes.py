from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user

from socialposter.core.email_sender import TEMPLATE_CONTENT, send_email, test_connection
from socialposter.web.models import EmailSetting, EmailTemplate, TEMPLATE_SEED, db

email_bp = Blueprint("email", __name__, url_prefix="/api/email")


def _seed_templates(user_id: int) -> None:
    existing = {
        t.type_key
        for t in EmailTemplate.query.filter_by(user_id=user_id).all()
    }
    for key, name in TEMPLATE_SEED:
        if key not in existing:
            db.session.add(EmailTemplate(user_id=user_id, type_key=key, name=name, enabled=True))
    db.session.commit()


def _settings_json(s: EmailSetting) -> dict:
    return {
        "from_name": s.from_name,
        "from_email": s.from_email,
        "reply_to_email": s.reply_to_email,
        "smtp_host": s.smtp_host,
        "smtp_port": s.smtp_port,
        "smtp_username": s.smtp_username,
        "smtp_has_password": bool(s.smtp_password),
    }


@email_bp.route("/settings", methods=["GET"])
def get_settings():
    s = EmailSetting.query.filter_by(user_id=current_user.id).first()
    if not s:
        s = EmailSetting(user_id=current_user.id)
        db.session.add(s)
        db.session.commit()
    return jsonify(_settings_json(s))


@email_bp.route("/settings", methods=["PUT"])
def update_settings():
    s = EmailSetting.query.filter_by(user_id=current_user.id).first()
    if not s:
        s = EmailSetting(user_id=current_user.id)
        db.session.add(s)
    data = request.get_json(force=True)
    if "from_name" in data:
        s.from_name = data["from_name"]
    if "from_email" in data:
        s.from_email = data["from_email"]
    if "reply_to_email" in data:
        s.reply_to_email = data["reply_to_email"]
    if "smtp_host" in data:
        s.smtp_host = data["smtp_host"]
    if "smtp_port" in data:
        s.smtp_port = data["smtp_port"]
    if "smtp_username" in data:
        s.smtp_username = data["smtp_username"]
    if "smtp_password" in data:
        s.smtp_password = data["smtp_password"]
    db.session.commit()
    return jsonify(_settings_json(s))


@email_bp.route("/test-connection", methods=["POST"])
def test_smtp_connection():
    s = EmailSetting.query.filter_by(user_id=current_user.id).first()
    if not s:
        return jsonify({"error": "No SMTP settings configured"}), 400
    if not s.smtp_host:
        return jsonify({"error": "SMTP host is required"}), 400

    result = test_connection(
        smtp_host=s.smtp_host,
        smtp_port=s.smtp_port,
        smtp_username=s.smtp_username,
        smtp_password=s.smtp_password,
    )
    return jsonify(result)


@email_bp.route("/templates/<int:template_id>/send-test", methods=["POST"])
def send_test_template(template_id: int):
    t = EmailTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
    if not t:
        return jsonify({"error": "Template not found"}), 404

    s = EmailSetting.query.filter_by(user_id=current_user.id).first()
    if not s or not s.smtp_host:
        return jsonify({"error": "SMTP not configured"}), 400

    content = TEMPLATE_CONTENT.get(t.type_key)
    subject = content[0] if content else t.name
    body = content[1] if content else f"This is a test email for: {t.name}"

    result = send_email(
        smtp_host=s.smtp_host,
        smtp_port=s.smtp_port,
        smtp_username=s.smtp_username,
        smtp_password=s.smtp_password,
        from_name=s.from_name,
        from_addr=s.from_email,
        reply_to=s.reply_to_email,
        to_addr=current_user.email,
        subject=f"[Test] {subject}",
        body_text=body,
    )
    return jsonify(result)
