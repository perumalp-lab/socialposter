"""Schedule blueprint – CRUD API for recurring scheduled posts."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from socialposter.utils.datetime import parse_user_datetime
from socialposter.web.models import ScheduledPost, ScheduleLog, db
from socialposter.web.token_auth import token_or_session_required

schedule_bp = Blueprint("schedule", __name__, url_prefix="/api/schedules")


def _serialize_schedule(sched: ScheduledPost) -> dict:
    return {
        "id": sched.id,
        "name": sched.name,
        "platforms": sched.platforms,
        "text": sched.text,
        "media": sched.media or [],
        "overrides": sched.overrides or {},
        "interval_minutes": sched.interval_minutes,
        "next_run_at": sched.next_run_at.isoformat() + "Z" if sched.next_run_at else None,
        "enabled": sched.enabled,
        "created_at": sched.created_at.isoformat() + "Z" if sched.created_at else None,
        "updated_at": sched.updated_at.isoformat() + "Z" if sched.updated_at else None,
    }


def _serialize_log(log: ScheduleLog) -> dict:
    return {
        "id": log.id,
        "schedule_id": log.schedule_id,
        "executed_at": log.executed_at.isoformat() + "Z" if log.executed_at else None,
        "results": log.results,
    }


@schedule_bp.route("", methods=["POST"])
@token_or_session_required
def create_schedule():
    data = request.get_json(force=True)

    name = data.get("name")
    platforms = data.get("platforms")
    text = data.get("text")
    interval_minutes = data.get("interval_minutes")
    start_at = data.get("start_at")

    if not name or not platforms or not text or not interval_minutes:
        return jsonify({"error": "name, platforms, text, and interval_minutes are required"}), 400

    if not isinstance(platforms, list) or not platforms:
        return jsonify({"error": "platforms must be a non-empty list"}), 400

    if not isinstance(interval_minutes, int) or interval_minutes < 1:
        return jsonify({"error": "interval_minutes must be a positive integer"}), 400

    if start_at:
        try:
            next_run = parse_user_datetime(start_at, current_user)
        except (ValueError, AttributeError):
            return jsonify({"error": "Invalid start_at format. Use ISO 8601."}), 400
    else:
        next_run = datetime.now(timezone.utc).replace(tzinfo=None)

    sched = ScheduledPost(
        user_id=current_user.id,
        name=name,
        platforms=platforms,
        text=text,
        media=data.get("media", []),
        overrides=data.get("overrides", {}),
        interval_minutes=interval_minutes,
        next_run_at=next_run,
    )
    db.session.add(sched)
    db.session.commit()

    return jsonify(_serialize_schedule(sched)), 201


@schedule_bp.route("", methods=["GET"])
@token_or_session_required
def list_schedules():
    schedules = ScheduledPost.query.filter_by(user_id=current_user.id).order_by(
        ScheduledPost.created_at.desc()
    ).all()
    return jsonify([_serialize_schedule(s) for s in schedules])


@schedule_bp.route("/<int:schedule_id>", methods=["GET"])
@token_or_session_required
def get_schedule(schedule_id: int):
    sched = ScheduledPost.query.filter_by(
        id=schedule_id, user_id=current_user.id
    ).first()
    if not sched:
        return jsonify({"error": "Schedule not found"}), 404

    recent_logs = (
        ScheduleLog.query.filter_by(schedule_id=sched.id)
        .order_by(ScheduleLog.executed_at.desc())
        .limit(10)
        .all()
    )

    result = _serialize_schedule(sched)
    result["recent_logs"] = [_serialize_log(log) for log in recent_logs]
    return jsonify(result)


@schedule_bp.route("/<int:schedule_id>", methods=["PUT"])
@token_or_session_required
def update_schedule(schedule_id: int):
    sched = ScheduledPost.query.filter_by(
        id=schedule_id, user_id=current_user.id
    ).first()
    if not sched:
        return jsonify({"error": "Schedule not found"}), 404

    data = request.get_json(force=True)

    if "name" in data:
        sched.name = data["name"]
    if "platforms" in data:
        if not isinstance(data["platforms"], list) or not data["platforms"]:
            return jsonify({"error": "platforms must be a non-empty list"}), 400
        sched.platforms = data["platforms"]
    if "text" in data:
        sched.text = data["text"]
    if "media" in data:
        sched.media = data["media"]
    if "overrides" in data:
        sched.overrides = data["overrides"]
    if "interval_minutes" in data:
        if not isinstance(data["interval_minutes"], int) or data["interval_minutes"] < 1:
            return jsonify({"error": "interval_minutes must be a positive integer"}), 400
        sched.interval_minutes = data["interval_minutes"]
    if "enabled" in data:
        sched.enabled = bool(data["enabled"])
    if "next_run_at" in data:
        try:
            sched.next_run_at = parse_user_datetime(data["next_run_at"], current_user)
        except (ValueError, AttributeError):
            return jsonify({"error": "Invalid next_run_at format. Use ISO 8601."}), 400

    db.session.commit()
    return jsonify(_serialize_schedule(sched))


@schedule_bp.route("/<int:schedule_id>", methods=["DELETE"])
@token_or_session_required
def delete_schedule(schedule_id: int):
    sched = ScheduledPost.query.filter_by(
        id=schedule_id, user_id=current_user.id
    ).first()
    if not sched:
        return jsonify({"error": "Schedule not found"}), 404

    db.session.delete(sched)
    db.session.commit()
    return jsonify({"ok": True})


@schedule_bp.route("/<int:schedule_id>/logs", methods=["GET"])
@token_or_session_required
def get_schedule_logs(schedule_id: int):
    sched = ScheduledPost.query.filter_by(
        id=schedule_id, user_id=current_user.id
    ).first()
    if not sched:
        return jsonify({"error": "Schedule not found"}), 404

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)

    logs = (
        ScheduleLog.query.filter_by(schedule_id=sched.id)
        .order_by(ScheduleLog.executed_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify({
        "schedule_id": sched.id,
        "page": page,
        "per_page": per_page,
        "logs": [_serialize_log(log) for log in logs],
    })
