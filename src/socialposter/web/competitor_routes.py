"""Competitor tracking API + dashboard page."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from socialposter.utils.datetime import isoformat_or
from socialposter.web.models import (
    CompetitorAccount, CompetitorPost, CompetitorAnalysis,
    PostHistory, EngagementMetric, db,
)
from socialposter.web.token_auth import token_or_session_required

log = logging.getLogger("socialposter")

competitor_bp = Blueprint("competitors", __name__)


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

@competitor_bp.route("/competitors")
@login_required
def competitors_page():
    return render_template("competitors.html")


# ---------------------------------------------------------------------------
# Competitor account CRUD
# ---------------------------------------------------------------------------

@competitor_bp.route("/api/competitors", methods=["GET"])
@token_or_session_required
def list_competitors():
    comps = CompetitorAccount.query.filter_by(user_id=current_user.id).order_by(
        CompetitorAccount.created_at.desc()
    ).all()
    return jsonify([
        {
            "id": c.id,
            "platform": c.platform,
            "handle": c.handle,
            "display_name": c.display_name,
            "is_active": c.is_active,
            "last_fetched_at": isoformat_or(c.last_fetched_at),
            "created_at": isoformat_or(c.created_at),
        }
        for c in comps
    ])


@competitor_bp.route("/api/competitors", methods=["POST"])
@token_or_session_required
def add_competitor():
    data = request.get_json(silent=True) or {}
    platform = (data.get("platform") or "").strip().lower()
    handle = (data.get("handle") or "").strip().lstrip("@")
    display_name = (data.get("display_name") or "").strip() or handle

    if not platform:
        return jsonify({"error": "Platform is required"}), 400
    if not handle:
        return jsonify({"error": "Handle is required"}), 400

    # Check for duplicate
    existing = CompetitorAccount.query.filter_by(
        user_id=current_user.id, platform=platform, handle=handle,
    ).first()
    if existing:
        return jsonify({"error": "Competitor already tracked"}), 409

    comp = CompetitorAccount(
        user_id=current_user.id,
        platform=platform,
        handle=handle,
        display_name=display_name,
    )
    db.session.add(comp)
    db.session.commit()
    return jsonify({"ok": True, "id": comp.id})


@competitor_bp.route("/api/competitors/<int:comp_id>", methods=["DELETE"])
@token_or_session_required
def delete_competitor(comp_id: int):
    comp = CompetitorAccount.query.filter_by(
        id=comp_id, user_id=current_user.id
    ).first()
    if not comp:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(comp)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Competitor posts
# ---------------------------------------------------------------------------

@competitor_bp.route("/api/competitors/<int:comp_id>/posts", methods=["GET"])
@token_or_session_required
def competitor_posts(comp_id: int):
    comp = CompetitorAccount.query.filter_by(
        id=comp_id, user_id=current_user.id
    ).first()
    if not comp:
        return jsonify({"error": "Not found"}), 404

    posts = CompetitorPost.query.filter_by(competitor_id=comp_id).order_by(
        CompetitorPost.posted_at.desc()
    ).limit(100).all()

    return jsonify([
        {
            "id": p.id,
            "platform_post_id": p.platform_post_id,
            "text": p.text,
            "likes": p.likes,
            "comments": p.comments,
            "shares": p.shares,
            "views": p.views,
            "posted_at": isoformat_or(p.posted_at),
        }
        for p in posts
    ])


@competitor_bp.route("/api/competitors/<int:comp_id>/fetch", methods=["POST"])
@token_or_session_required
def fetch_competitor(comp_id: int):
    """Manual trigger to fetch competitor posts."""
    comp = CompetitorAccount.query.filter_by(
        id=comp_id, user_id=current_user.id
    ).first()
    if not comp:
        return jsonify({"error": "Not found"}), 404

    from flask import current_app
    from socialposter.core.competitor_service import fetch_competitor_posts

    try:
        count = fetch_competitor_posts(current_app._get_current_object(), comp_id)
        return jsonify({"ok": True, "new_posts": count})
    except Exception as e:
        log.exception("Manual competitor fetch failed")
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# AI Analysis
# ---------------------------------------------------------------------------

@competitor_bp.route("/api/competitors/analysis", methods=["GET"])
@token_or_session_required
def get_analysis():
    """Generate or retrieve competitor analysis."""
    competitor_ids_str = request.args.get("competitor_ids", "")
    period_days = int(request.args.get("period_days", "30"))

    if competitor_ids_str:
        competitor_ids = [int(x) for x in competitor_ids_str.split(",") if x.strip()]
    else:
        # All active competitors
        comps = CompetitorAccount.query.filter_by(
            user_id=current_user.id, is_active=True
        ).all()
        competitor_ids = [c.id for c in comps]

    if not competitor_ids:
        return jsonify({"error": "No competitors to analyze"}), 400

    from socialposter.core.competitor_service import generate_competitor_analysis

    try:
        analysis = generate_competitor_analysis(current_user.id, competitor_ids, period_days)
        return jsonify({"analysis": analysis})
    except Exception as e:
        log.exception("Competitor analysis failed")
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# Engagement comparison
# ---------------------------------------------------------------------------

@competitor_bp.route("/api/competitors/compare", methods=["GET"])
@token_or_session_required
def compare_engagement():
    """Compare user's engagement with competitors."""
    period_days = int(request.args.get("period_days", "30"))
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    # User's metrics
    user_metrics = EngagementMetric.query.filter(
        EngagementMetric.user_id == current_user.id,
        EngagementMetric.fetched_at >= since,
    ).all()

    user_total = {
        "likes": sum(m.likes for m in user_metrics),
        "comments": sum(m.comments for m in user_metrics),
        "shares": sum(m.shares for m in user_metrics),
        "posts": len(user_metrics),
    }

    # Competitors' metrics
    comps = CompetitorAccount.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()

    comp_data = []
    for comp in comps:
        posts = CompetitorPost.query.filter(
            CompetitorPost.competitor_id == comp.id,
        ).all()
        comp_data.append({
            "handle": comp.handle,
            "platform": comp.platform,
            "likes": sum(p.likes for p in posts),
            "comments": sum(p.comments for p in posts),
            "shares": sum(p.shares for p in posts),
            "posts": len(posts),
        })

    return jsonify({
        "user": user_total,
        "competitors": comp_data,
        "period_days": period_days,
    })
