"""RQ job functions executed by the worker process.

Each job is self-contained: it builds (or reuses) a Flask app, opens an app
context, and does its work. Jobs take primitive IDs as arguments — never live
ORM objects — so RQ can serialise them.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("socialposter")

_app = None


def _get_app():
    """Build (and cache) a Flask app for the worker process."""
    global _app
    if _app is not None:
        return _app

    os.environ.setdefault("SOCIALPOSTER_SKIP_SCHEDULER", "1")
    from socialposter.web.app import create_app

    _app = create_app()
    return _app


def reset_app_for_testing(app=None) -> None:
    """Inject (or clear) the cached app — used by the test suite."""
    global _app
    _app = app


# ---------------------------------------------------------------------------
# Scheduled post publishing
# ---------------------------------------------------------------------------

def publish_scheduled_post(schedule_id: int, platform_name: str) -> dict:
    """Publish a single (schedule × platform) combination.

    Returns a serialisable result dict. Records a ``ScheduleLog`` row, a
    ``PostHistory`` entry, and (on success) a ``PublishedPost``.
    """
    app = _get_app()
    with app.app_context():
        from socialposter.core.publisher import _publish_one, _resolve_platforms
        from socialposter.core.scheduler import _build_post_file
        from socialposter.utils.publishing import record_published_post
        from socialposter.utils.team import get_current_team_id
        from socialposter.web.models import (
            ScheduledPost, ScheduleLog, db, record_post_history,
        )

        sched = db.session.get(ScheduledPost, schedule_id)
        if not sched or not sched.enabled:
            return {"skipped": True, "reason": "not_found_or_disabled"}

        content = _build_post_file(sched)
        platforms = _resolve_platforms(content, [platform_name])
        if not platforms:
            return {"skipped": True, "reason": "platform_unknown"}

        try:
            result = _publish_one(
                platforms[0], content, dry_run=False, user_id=sched.user_id
            )
        except Exception as exc:
            logger.exception(
                "Publish job crashed for schedule %d platform %s",
                schedule_id, platform_name,
            )
            db.session.rollback()
            raise  # let RQ retry

        result_dict = {
            "platform": result.platform,
            "success": result.success,
            "post_id": result.post_id,
            "post_url": result.post_url,
            "error": result.error_message,
        }

        record_post_history(
            user_id=sched.user_id,
            platform=result.platform,
            text=sched.text,
            success=result.success,
            schedule_id=sched.id,
            media=sched.media,
            post_id=result.post_id,
            post_url=result.post_url,
            error_message=result.error_message,
        )

        if result.success and result.post_id:
            record_published_post(
                user_id=sched.user_id,
                team_id=get_current_team_id(sched.user_id),
                result=result,
                text_preview=sched.text or "",
            )

        try:
            db.session.add(ScheduleLog(schedule_id=sched.id, results=[result_dict]))
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Failed to record ScheduleLog for schedule %d", sched.id)

        if not result.success:
            # Surface failure to RQ so the retry policy kicks in.
            raise RuntimeError(
                f"{platform_name} publish failed: {result.error_message or 'unknown'}"
            )

        return result_dict


# ---------------------------------------------------------------------------
# Comment fetching
# ---------------------------------------------------------------------------

def fetch_post_comments(published_post_id: int) -> dict:
    """Fetch new comments for a single published post."""
    app = _get_app()
    with app.app_context():
        from socialposter.platforms.registry import PlatformRegistry
        from socialposter.web.models import (
            InboxComment, PublishedPost, db,
        )

        post = db.session.get(PublishedPost, published_post_id)
        if not post:
            return {"skipped": True, "reason": "post_not_found"}

        platform_cls = PlatformRegistry.all().get(post.platform)
        if not platform_cls:
            return {"skipped": True, "reason": "platform_unknown"}

        platform_instance = platform_cls()
        if not platform_instance.supports_comment_fetching():
            return {"skipped": True, "reason": "unsupported"}

        since = post.last_comment_fetch
        comments = platform_instance.fetch_comments(
            post.user_id, post.platform_post_id, since=since
        )

        added = 0
        for c in comments:
            existing = InboxComment.query.filter_by(
                platform=post.platform,
                platform_comment_id=c.get("comment_id", ""),
            ).first()
            if existing:
                continue
            ic = InboxComment(
                team_id=post.team_id,
                platform=post.platform,
                platform_comment_id=c.get("comment_id", ""),
                platform_post_id=post.platform_post_id,
                platform_post_url=post.platform_post_url,
                author_name=c.get("author_name", ""),
                author_profile_url=c.get("author_profile_url", ""),
                author_avatar_url=c.get("author_avatar_url", ""),
                text=c.get("text", ""),
                parent_comment_id=c.get("parent_comment_id"),
                posted_at=c.get("posted_at"),
            )
            db.session.add(ic)
            added += 1

        post.last_comment_fetch = datetime.now(timezone.utc)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(
                "Failed to persist comments for published_post %d", published_post_id
            )
            raise

        return {"published_post_id": published_post_id, "added": added}


# ---------------------------------------------------------------------------
# Engagement fetching
# ---------------------------------------------------------------------------

def fetch_post_engagement(published_post_id: int) -> dict:
    """Fetch engagement metrics for a single published post."""
    app = _get_app()
    with app.app_context():
        from socialposter.platforms.registry import PlatformRegistry
        from socialposter.web.models import EngagementMetric, PublishedPost, db

        post = db.session.get(PublishedPost, published_post_id)
        if not post:
            return {"skipped": True, "reason": "post_not_found"}

        platform_cls = PlatformRegistry.all().get(post.platform)
        if not platform_cls:
            return {"skipped": True, "reason": "platform_unknown"}

        platform_instance = platform_cls()
        if not platform_instance.supports_engagement_fetching():
            return {"skipped": True, "reason": "unsupported"}

        metrics = platform_instance.fetch_engagement(
            post.user_id, post.platform_post_id
        )
        if not metrics:
            return {"skipped": True, "reason": "no_metrics"}

        total = (
            metrics.get("likes", 0)
            + metrics.get("comments", 0)
            + metrics.get("shares", 0)
        )
        views = metrics.get("views", 0)
        rate = round((total / views * 100) if views else 0.0, 2)

        em = EngagementMetric(
            user_id=post.user_id,
            published_post_id=post.id,
            platform=post.platform,
            likes=metrics.get("likes", 0),
            comments=metrics.get("comments", 0),
            shares=metrics.get("shares", 0),
            views=views,
            clicks=metrics.get("clicks", 0),
            engagement_rate=rate,
        )
        db.session.add(em)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(
                "Failed to persist engagement for published_post %d", published_post_id
            )
            raise

        return {"published_post_id": published_post_id, "engagement_rate": rate}
