"""Integration tests for the analytics dashboard endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _add_history(
    db, user_id, *, platform="linkedin", success=True, when=None, text="hello",
):
    from socialposter.web.models import PostHistory
    row = PostHistory(
        user_id=user_id,
        platform=platform,
        text=text,
        post_id="x",
        post_url="",
        success=success,
        created_at=(when or datetime.now(timezone.utc)).replace(tzinfo=None),
    )
    db.session.add(row)
    db.session.commit()
    return row


def _wipe_history(db, user_id):
    from socialposter.web.models import PostHistory
    PostHistory.query.filter_by(user_id=user_id).delete()
    db.session.commit()


# ── /api/analytics/summary ──


def test_summary_counts_and_success_rate(client, db, test_user):
    now = datetime.now(timezone.utc)
    try:
        _add_history(db, test_user.id, platform="linkedin", success=True, when=now)
        _add_history(db, test_user.id, platform="linkedin", success=True, when=now)
        _add_history(db, test_user.id, platform="twitter", success=True, when=now)
        _add_history(db, test_user.id, platform="twitter", success=False, when=now)

        resp = client.get("/api/analytics/summary?days=30")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] == 4
        assert body["successes"] == 3
        assert body["success_rate"] == 75.0
        assert body["top_platform"] == "linkedin"
        assert body["platform_breakdown"]["linkedin"] == 2
        assert body["platform_breakdown"]["twitter"] == 2
    finally:
        _wipe_history(db, test_user.id)


def test_summary_excludes_rows_outside_window(client, db, test_user):
    """A row older than `days` ago should not be counted."""
    now = datetime.now(timezone.utc)
    try:
        _add_history(db, test_user.id, when=now)  # in window
        _add_history(db, test_user.id, when=now - timedelta(days=45))  # outside
        resp = client.get("/api/analytics/summary?days=30")
        body = resp.get_json()
        assert body["total"] == 1
    finally:
        _wipe_history(db, test_user.id)


def test_summary_empty_history_returns_zero_rate(client, db, test_user):
    _wipe_history(db, test_user.id)
    resp = client.get("/api/analytics/summary?days=30")
    body = resp.get_json()
    assert body["total"] == 0
    assert body["success_rate"] == 0
    assert body["top_platform"] == ""


# ── /api/analytics/timeline ──


def test_timeline_fills_zero_days(client, db, test_user):
    """Days with no posts should be present with count=0."""
    now = datetime.now(timezone.utc)
    try:
        _add_history(db, test_user.id, when=now)
        resp = client.get("/api/analytics/timeline?days=7")
        body = resp.get_json()
        # 8 days inclusive (since-day through today)
        assert len(body["timeline"]) >= 7
        # Today's entry should have count >= 1
        today_str = now.date().isoformat()
        today_entry = next(p for p in body["timeline"] if p["date"] == today_str)
        assert today_entry["count"] >= 1
        # At least one zero-count day exists in the gap-filled range
        zero_days = [p for p in body["timeline"] if p["count"] == 0]
        assert len(zero_days) >= 1
    finally:
        _wipe_history(db, test_user.id)


# ── /api/analytics/heatmap ──


def _last_wednesday_at(hour: int) -> datetime:
    """Return the most recent Wednesday at `hour` UTC, in the past."""
    now = datetime.now(timezone.utc)
    # Python weekday: Mon=0..Sun=6. Wed=2. Walk backwards to find the previous Wed.
    delta = (now.weekday() - 2) % 7 or 7
    base = (now - timedelta(days=delta)).replace(
        hour=hour, minute=0, second=0, microsecond=0,
    )
    return base


def test_heatmap_normalizes_weekday_to_monday_first(client, db, test_user):
    """SQLite %w is Sunday-first (0=Sun); endpoint must remap to Monday-first."""
    wed = _last_wednesday_at(14)
    try:
        _add_history(db, test_user.id, when=wed, success=True)
        _add_history(db, test_user.id, when=wed, success=True)

        resp = client.get("/api/analytics/heatmap?days=90")
        body = resp.get_json()
        cells = body["cells"]
        # Wednesday in Mon-first indexing is weekday=2.
        wed_cells = [c for c in cells if c["weekday"] == 2 and c["hour"] == 14]
        assert wed_cells, f"no Wed 14h cell in {cells}"
        assert wed_cells[0]["count"] == 2
        # All weekday values should be in [0, 6].
        assert all(0 <= c["weekday"] <= 6 for c in cells)
    finally:
        _wipe_history(db, test_user.id)


def test_heatmap_excludes_failed_posts(client, db, test_user):
    """Heatmap reflects successful posts only — failed publishes are not 'posting activity'."""
    when = _last_wednesday_at(10) + timedelta(days=1)  # Thursday
    try:
        _add_history(db, test_user.id, when=when, success=False)
        resp = client.get("/api/analytics/heatmap?days=90")
        body = resp.get_json()
        # Thursday=3 in Mon-first. The failed row must NOT appear.
        thur_cells = [c for c in body["cells"] if c["weekday"] == 3 and c["hour"] == 10]
        assert thur_cells == []
    finally:
        _wipe_history(db, test_user.id)
