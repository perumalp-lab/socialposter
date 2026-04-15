"""Analytics blueprint – dashboard, summary, timeline, and history APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from socialposter.utils.datetime import isoformat_or
from socialposter.utils.pagination import paginate_query
from socialposter.web.models import PostHistory, EngagementMetric, PublishedPost, db

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics")
@login_required
def dashboard():
    return render_template("analytics.html")


@analytics_bp.route("/api/analytics/summary")
@login_required
def api_summary():
    days = request.args.get("days", 30, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base = PostHistory.query.filter(
        PostHistory.user_id == current_user.id,
        PostHistory.created_at >= since,
    )

    total = base.count()
    successes = base.filter(PostHistory.success == True).count()  # noqa: E712
    success_rate = round((successes / total * 100) if total else 0, 1)

    # Platform breakdown
    platform_rows = (
        db.session.query(PostHistory.platform, func.count(PostHistory.id))
        .filter(
            PostHistory.user_id == current_user.id,
            PostHistory.created_at >= since,
        )
        .group_by(PostHistory.platform)
        .all()
    )
    platform_breakdown = {row[0]: row[1] for row in platform_rows}
    top_platform = max(platform_breakdown, key=platform_breakdown.get) if platform_breakdown else ""

    return jsonify({
        "total": total,
        "successes": successes,
        "success_rate": success_rate,
        "top_platform": top_platform,
        "platform_breakdown": platform_breakdown,
        "days": days,
    })


@analytics_bp.route("/api/analytics/timeline")
@login_required
def api_timeline():
    days = request.args.get("days", 30, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.session.query(
            func.date(PostHistory.created_at).label("day"),
            func.count(PostHistory.id).label("count"),
        )
        .filter(
            PostHistory.user_id == current_user.id,
            PostHistory.created_at >= since,
        )
        .group_by(func.date(PostHistory.created_at))
        .order_by(func.date(PostHistory.created_at))
        .all()
    )

    timeline = []
    day_map = {str(r.day): r.count for r in rows}
    current = since.date()
    end = datetime.now(timezone.utc).date()
    while current <= end:
        key = str(current)
        timeline.append({"date": key, "count": day_map.get(key, 0)})
        current += timedelta(days=1)

    return jsonify({"timeline": timeline, "days": days})


@analytics_bp.route("/api/analytics/history")
@login_required
def api_history():
    page = request.args.get("page", 1, type=int)
    per_page = 20
    platform_filter = request.args.get("platform", "")
    success_filter = request.args.get("success", "")

    query = PostHistory.query.filter(PostHistory.user_id == current_user.id)

    if platform_filter:
        query = query.filter(PostHistory.platform == platform_filter)
    if success_filter == "true":
        query = query.filter(PostHistory.success == True)  # noqa: E712
    elif success_filter == "false":
        query = query.filter(PostHistory.success == False)  # noqa: E712

    query = query.order_by(PostHistory.created_at.desc())

    def _serialize(h):
        return {
            "id": h.id,
            "platform": h.platform,
            "text": h.text[:200],
            "success": h.success,
            "post_url": h.post_url,
            "error_message": h.error_message,
            "created_at": isoformat_or(h.created_at),
        }

    return jsonify(paginate_query(query, page, serializer=_serialize))


@analytics_bp.route("/api/analytics/engagement")
@login_required
def api_engagement():
    """Per-platform engagement aggregates for the given period."""
    days = request.args.get("days", 30, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.session.query(
            EngagementMetric.platform,
            func.sum(EngagementMetric.likes).label("likes"),
            func.sum(EngagementMetric.comments).label("comments"),
            func.sum(EngagementMetric.shares).label("shares"),
            func.sum(EngagementMetric.views).label("views"),
            func.sum(EngagementMetric.clicks).label("clicks"),
            func.avg(EngagementMetric.engagement_rate).label("avg_rate"),
            func.count(EngagementMetric.id).label("count"),
        )
        .filter(
            EngagementMetric.user_id == current_user.id,
            EngagementMetric.fetched_at >= since,
        )
        .group_by(EngagementMetric.platform)
        .all()
    )

    platforms = {}
    totals = {"likes": 0, "comments": 0, "shares": 0, "views": 0, "clicks": 0}
    for r in rows:
        entry = {
            "likes": r.likes or 0,
            "comments": r.comments or 0,
            "shares": r.shares or 0,
            "views": r.views or 0,
            "clicks": r.clicks or 0,
            "avg_engagement_rate": round(r.avg_rate or 0, 2),
            "count": r.count or 0,
        }
        platforms[r.platform] = entry
        for k in totals:
            totals[k] += entry[k]

    return jsonify({"platforms": platforms, "totals": totals, "days": days})


@analytics_bp.route("/api/analytics/best-times")
@login_required
def api_best_times():
    """Best posting hours by average engagement."""
    rows = (
        db.session.query(
            func.strftime("%H", PostHistory.created_at).label("hour"),
            func.count(PostHistory.id).label("post_count"),
        )
        .filter(
            PostHistory.user_id == current_user.id,
            PostHistory.success == True,  # noqa: E712
        )
        .group_by(func.strftime("%H", PostHistory.created_at))
        .all()
    )

    # Build engagement per hour from EngagementMetric
    eng_rows = (
        db.session.query(
            func.strftime("%H", EngagementMetric.fetched_at).label("hour"),
            func.avg(EngagementMetric.engagement_rate).label("avg_rate"),
        )
        .filter(EngagementMetric.user_id == current_user.id)
        .group_by(func.strftime("%H", EngagementMetric.fetched_at))
        .all()
    )
    eng_by_hour = {r.hour: round(r.avg_rate or 0, 2) for r in eng_rows}

    hours = []
    for r in rows:
        hours.append({
            "hour": int(r.hour),
            "post_count": r.post_count,
            "avg_engagement_rate": eng_by_hour.get(r.hour, 0),
        })
    hours.sort(key=lambda x: x["avg_engagement_rate"], reverse=True)

    return jsonify({"hours": hours})


@analytics_bp.route("/api/analytics/top-posts")
@login_required
def api_top_posts():
    """Top 5 posts by total engagement."""
    days = request.args.get("days", 30, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get the latest engagement metric per published post
    subq = (
        db.session.query(
            EngagementMetric.published_post_id,
            func.max(EngagementMetric.fetched_at).label("max_fetched"),
        )
        .filter(
            EngagementMetric.user_id == current_user.id,
            EngagementMetric.fetched_at >= since,
            EngagementMetric.published_post_id.isnot(None),
        )
        .group_by(EngagementMetric.published_post_id)
        .subquery()
    )

    rows = (
        db.session.query(EngagementMetric, PublishedPost)
        .join(subq, db.and_(
            EngagementMetric.published_post_id == subq.c.published_post_id,
            EngagementMetric.fetched_at == subq.c.max_fetched,
        ))
        .join(PublishedPost, PublishedPost.id == EngagementMetric.published_post_id)
        .filter(EngagementMetric.user_id == current_user.id)
        .order_by(
            (EngagementMetric.likes + EngagementMetric.comments + EngagementMetric.shares).desc()
        )
        .limit(5)
        .all()
    )

    posts = []
    for em, pp in rows:
        posts.append({
            "platform": em.platform,
            "text_preview": pp.text_preview,
            "post_url": pp.platform_post_url,
            "likes": em.likes,
            "comments": em.comments,
            "shares": em.shares,
            "views": em.views,
            "engagement_rate": em.engagement_rate,
            "published_at": isoformat_or(pp.published_at),
        })

    return jsonify({"posts": posts, "days": days})
