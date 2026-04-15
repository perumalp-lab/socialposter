"""Calendar blueprint – month view with scheduled and published posts."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from socialposter.utils.datetime import get_user_tz
from socialposter.web.models import PostHistory, ScheduledPost

calendar_bp = Blueprint("calendar_view", __name__)


@calendar_bp.route("/calendar")
@login_required
def calendar_page():
    return render_template("calendar.html")


@calendar_bp.route("/api/calendar/events")
@login_required
def api_calendar_events():
    year = request.args.get("year", datetime.now(timezone.utc).year, type=int)
    month = request.args.get("month", datetime.now(timezone.utc).month, type=int)

    _, last_day = calendar.monthrange(year, month)
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    # Published posts in this month
    history = PostHistory.query.filter(
        PostHistory.user_id == current_user.id,
        PostHistory.created_at >= start,
        PostHistory.created_at <= end,
    ).all()

    # Scheduled posts with next_run_at in this month
    scheduled = ScheduledPost.query.filter(
        ScheduledPost.user_id == current_user.id,
        ScheduledPost.enabled == True,  # noqa: E712
        ScheduledPost.next_run_at >= start,
        ScheduledPost.next_run_at <= end,
    ).all()

    # Convert UTC datetimes to the user's timezone for display
    user_tz = get_user_tz(current_user)

    events = []

    for h in history:
        local_dt = h.created_at.replace(tzinfo=timezone.utc).astimezone(user_tz)
        events.append({
            "type": "published",
            "date": local_dt.strftime("%Y-%m-%d"),
            "time": local_dt.strftime("%H:%M"),
            "platform": h.platform,
            "text": h.text[:100],
            "success": h.success,
            "post_url": h.post_url,
        })

    for s in scheduled:
        local_dt = s.next_run_at.replace(tzinfo=timezone.utc).astimezone(user_tz)
        events.append({
            "type": "scheduled",
            "date": local_dt.strftime("%Y-%m-%d"),
            "time": local_dt.strftime("%H:%M"),
            "platform": ",".join(s.platforms) if s.platforms else "",
            "text": s.text[:100],
            "name": s.name,
            "schedule_id": s.id,
        })

    return jsonify({
        "year": year,
        "month": month,
        "timezone": current_user.timezone,
        "events": events,
    })
