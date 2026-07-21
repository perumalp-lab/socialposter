from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from socialposter.web.models import PlatformIntegration, db

integration_bp = Blueprint("integration", __name__, url_prefix="/api/integrations")


@integration_bp.route("/settings", methods=["GET"])
def get_settings():
    s = PlatformIntegration.query.filter_by(user_id=current_user.id).first()
    if not s:
        s = PlatformIntegration(user_id=current_user.id)
        db.session.add(s)
        db.session.commit()
    return jsonify({
        "zapier_api_key": s.zapier_api_key,
        "pabbly_api_key": s.pabbly_api_key,
    })


@integration_bp.route("/settings", methods=["PUT"])
def update_settings():
    s = PlatformIntegration.query.filter_by(user_id=current_user.id).first()
    if not s:
        s = PlatformIntegration(user_id=current_user.id)
        db.session.add(s)
    data = request.get_json(force=True)
    if "zapier_api_key" in data:
        s.zapier_api_key = data["zapier_api_key"]
    if "pabbly_api_key" in data:
        s.pabbly_api_key = data["pabbly_api_key"]
    db.session.commit()
    return jsonify({
        "zapier_api_key": s.zapier_api_key,
        "pabbly_api_key": s.pabbly_api_key,
    })
