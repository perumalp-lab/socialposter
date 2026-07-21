from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user

from socialposter.web.models import Webinar, EmailSetting, db, log_activity
from socialposter.web.token_auth import token_or_session_required
from socialposter.core.email_sender import send_email

webinar_bp = Blueprint("webinar", __name__, url_prefix="/api/webinars")


def _serialize(w: Webinar) -> dict:
    return {
        "id": w.id,
        "title": w.title,
        "description": w.description,
        "scheduled_at": w.scheduled_at.isoformat() + "Z" if w.scheduled_at else None,
        "duration_minutes": w.duration_minutes,
        "platform_type": w.platform_type,
        "meeting_url": w.meeting_url,
        "registration_url": w.registration_url,
        "recording_url": w.recording_url,
        "host_name": w.host_name,
        "target_audience": w.target_audience,
        "timezone": w.timezone,
        "tags": w.tags or [],
        "max_attendees": w.max_attendees,
        "status": w.status,
        "attendees": w.attendees or [],
        "invitations_sent_at": w.invitations_sent_at.isoformat() + "Z" if w.invitations_sent_at else None,
        "created_at": w.created_at.isoformat() + "Z" if w.created_at else None,
        "updated_at": w.updated_at.isoformat() + "Z" if w.updated_at else None,
    }


@webinar_bp.route("", methods=["POST"])
@token_or_session_required
def create_webinar():
    data = request.get_json(force=True)
    title = data.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400

    scheduled_at = None
    if data.get("scheduled_at"):
        try:
            scheduled_at = datetime.fromisoformat(data["scheduled_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return jsonify({"error": "Invalid scheduled_at format"}), 400

    w = Webinar(
        user_id=current_user.id,
        title=title,
        description=data.get("description", ""),
        scheduled_at=scheduled_at,
        duration_minutes=data.get("duration_minutes", 60),
        platform_type=data.get("platform_type", "zoom"),
        meeting_url=data.get("meeting_url", ""),
        registration_url=data.get("registration_url", ""),
        recording_url=data.get("recording_url", ""),
        host_name=data.get("host_name", ""),
        target_audience=data.get("target_audience", ""),
        timezone=data.get("timezone", "UTC"),
        tags=data.get("tags", []),
        max_attendees=data.get("max_attendees"),
        status=data.get("status", "draft"),
        attendees=data.get("attendees", []),
    )
    db.session.add(w)
    db.session.commit()
    log_activity(current_user.id, "webinar.create", target_type="webinar", target_id=w.id, details={"title": w.title})
    return jsonify(_serialize(w)), 201


@webinar_bp.route("", methods=["GET"])
@token_or_session_required
def list_webinars():
    webinars = Webinar.query.filter_by(user_id=current_user.id).order_by(Webinar.created_at.desc()).all()
    return jsonify([_serialize(w) for w in webinars])


@webinar_bp.route("/<int:webinar_id>", methods=["GET"])
@token_or_session_required
def get_webinar(webinar_id: int):
    w = Webinar.query.filter_by(id=webinar_id, user_id=current_user.id).first()
    if not w:
        return jsonify({"error": "Webinar not found"}), 404
    return jsonify(_serialize(w))


@webinar_bp.route("/<int:webinar_id>", methods=["PUT"])
@token_or_session_required
def update_webinar(webinar_id: int):
    w = Webinar.query.filter_by(id=webinar_id, user_id=current_user.id).first()
    if not w:
        return jsonify({"error": "Webinar not found"}), 404

    data = request.get_json(force=True)
    if "title" in data:
        w.title = data["title"]
    if "description" in data:
        w.description = data["description"]
    if "scheduled_at" in data:
        try:
            w.scheduled_at = datetime.fromisoformat(data["scheduled_at"].replace("Z", "+00:00")).replace(tzinfo=None) if data["scheduled_at"] else None
        except (ValueError, AttributeError):
            return jsonify({"error": "Invalid scheduled_at format"}), 400
    if "duration_minutes" in data:
        w.duration_minutes = data["duration_minutes"]
    if "platform_type" in data:
        w.platform_type = data["platform_type"]
    if "meeting_url" in data:
        w.meeting_url = data["meeting_url"]
    if "registration_url" in data:
        w.registration_url = data["registration_url"]
    if "recording_url" in data:
        w.recording_url = data["recording_url"]
    if "host_name" in data:
        w.host_name = data["host_name"]
    if "target_audience" in data:
        w.target_audience = data["target_audience"]
    if "timezone" in data:
        w.timezone = data["timezone"]
    if "tags" in data:
        w.tags = data["tags"]
    if "max_attendees" in data:
        w.max_attendees = data["max_attendees"]
    if "status" in data:
        w.status = data["status"]
    if "attendees" in data:
        w.attendees = data["attendees"]

    db.session.commit()
    return jsonify(_serialize(w))


@webinar_bp.route("/<int:webinar_id>", methods=["DELETE"])
@token_or_session_required
def delete_webinar(webinar_id: int):
    w = Webinar.query.filter_by(id=webinar_id, user_id=current_user.id).first()
    if not w:
        return jsonify({"error": "Webinar not found"}), 404
    db.session.delete(w)
    db.session.commit()
    return jsonify({"ok": True})


@webinar_bp.route("/<int:webinar_id>/send-invitations", methods=["POST"])
@token_or_session_required
def send_invitations(webinar_id: int):
    w = Webinar.query.filter_by(id=webinar_id, user_id=current_user.id).first()
    if not w:
        return jsonify({"error": "Webinar not found"}), 404
    if not w.attendees:
        return jsonify({"error": "No attendees to invite"}), 400

    settings = EmailSetting.query.filter_by(user_id=current_user.id).first()
    if not settings or not settings.smtp_host:
        return jsonify({"error": "Email settings not configured. Go to Automation > Email to set up SMTP."}), 400

    tz_display = f" ({w.timezone})" if w.timezone else ""
    scheduled_str = w.scheduled_at.strftime("%B %d, %Y at %I:%M %p") + tz_display if w.scheduled_at else "To be announced"
    meeting_info = f"\nMeeting link: {w.meeting_url}" if w.meeting_url else ""
    registration_info = f"\nRegistration: {w.registration_url}" if w.registration_url else ""
    recording_info = f"\nRecording: {w.recording_url}" if w.recording_url else ""

    results = []
    for attendee in w.attendees:
        email = attendee.get("email")
        name = attendee.get("name", "")
        if not email:
            continue
        greeting = f"Hi {name}," if name else "Hi there,"
        body = (
            f"{greeting}\n\n"
            f"You are invited to \"{w.title}\".\n\n"
            f"When: {scheduled_str}\n"
            f"Duration: {w.duration_minutes} minutes\n"
            f"Host: {w.host_name or 'TBD'}{meeting_info}{registration_info}{recording_info}"
        )
        result = send_email(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            from_name=settings.from_name,
            from_addr=settings.from_email,
            reply_to=settings.reply_to_email,
            to_addr=email,
            subject=f"Invitation: {w.title}",
            body_text=body,
        )
        results.append({"email": email, "ok": result.get("ok", False), "error": result.get("error")})

    w.invitations_sent_at = datetime.utcnow()
    db.session.commit()
    log_activity(
        current_user.id, "webinar.invite",
        target_type="webinar", target_id=w.id,
        details={"title": w.title, "count": len(w.attendees), "results": results},
    )

    success_count = sum(1 for r in results if r["ok"])
    error_count = sum(1 for r in results if not r.get("ok"))
    return jsonify({
        "ok": True,
        "invitations_sent_at": w.invitations_sent_at.isoformat() + "Z",
        "results": results,
        "success_count": success_count,
        "error_count": error_count,
    })
