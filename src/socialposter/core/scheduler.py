"""Background scheduler – claims due ScheduledPost rows and dispatches work.

When ``REDIS_URL`` is configured, due rows are dispatched as RQ jobs. Without
Redis, the scheduler falls back to in-process execution (preserving local-dev
behavior without requiring Redis).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from socialposter.core.content import (
    DefaultContent,
    MediaItem,
    PlatformOverrides,
    PostFile,
    FacebookOverride,
    InstagramOverride,
    LinkedInOverride,
    TwitterOverride,
    WhatsAppOverride,
    YouTubeOverride,
)

logger = logging.getLogger("socialposter")


# Don't re-enqueue comment fetches while a previous round may still be in flight.
# Must comfortably exceed worker drain time for a single comment fetch.
COMMENT_FETCH_COOLDOWN = timedelta(minutes=4)


def _build_post_file(sched) -> PostFile:
    """Construct a PostFile from a ScheduledPost row's stored JSON fields."""
    media_items = []
    for m in (sched.media or []):
        media_items.append(
            MediaItem(
                path=m["path"],
                type=m.get("media_type", "image"),
                alt_text=m.get("alt_text"),
            )
        )

    defaults = DefaultContent(text=sched.text, media=media_items)

    overrides_kwargs = {}
    raw_overrides = sched.overrides or {}
    for pname in sched.platforms:
        ov = raw_overrides.get(pname, {})
        if pname == "linkedin":
            overrides_kwargs["linkedin"] = LinkedInOverride(enabled=True, text=ov.get("text"), visibility=ov.get("visibility", "public"))
        elif pname == "youtube":
            overrides_kwargs["youtube"] = YouTubeOverride(enabled=True, title=ov.get("title"), description=ov.get("description"), tags=ov.get("tags", []), privacy=ov.get("privacy", "public"))
        elif pname == "instagram":
            overrides_kwargs["instagram"] = InstagramOverride(enabled=True, text=ov.get("text"), post_type=ov.get("post_type", "feed"))
        elif pname == "facebook":
            overrides_kwargs["facebook"] = FacebookOverride(enabled=True, text=ov.get("text"), link=ov.get("link"))
        elif pname == "twitter":
            overrides_kwargs["twitter"] = TwitterOverride(enabled=True, text=ov.get("text"))
        elif pname == "whatsapp":
            overrides_kwargs["whatsapp"] = WhatsAppOverride(enabled=True, text=ov.get("text"), recipients=ov.get("recipients", []))

    return PostFile(defaults=defaults, platforms=PlatformOverrides(**overrides_kwargs))


def _claim_due_posts(now: datetime) -> list:
    """Optimistically claim due schedules by advancing ``next_run_at``.

    The atomic UPDATE protects against duplicate dispatch when multiple
    gunicorn workers run the scheduler in parallel.
    """
    from socialposter.web.models import ScheduledPost, db

    due = ScheduledPost.query.filter(
        ScheduledPost.enabled == True,  # noqa: E712
        ScheduledPost.next_run_at <= now,
    ).all()

    claimed = []
    for sched in due:
        original = sched.next_run_at
        new_next_run = original + timedelta(minutes=sched.interval_minutes)
        rows_affected = ScheduledPost.query.filter(
            ScheduledPost.id == sched.id,
            ScheduledPost.next_run_at == original,
            ScheduledPost.enabled == True,  # noqa: E712
        ).update(
            {"next_run_at": new_next_run},
            synchronize_session=False,
        )
        if rows_affected == 1:
            db.session.commit()
            claimed.append(sched)
        else:
            db.session.rollback()
    return claimed


def _execute_due_posts(app):
    """Called by APScheduler every 30 seconds inside the Flask app context."""
    with app.app_context():
        from socialposter.core import queue as task_queue
        from socialposter.core.jobs import publish_scheduled_post

        now = datetime.now(timezone.utc)
        claimed = _claim_due_posts(now)

        if not claimed:
            return

        if task_queue.is_enabled():
            for sched in claimed:
                for platform_name in sched.platforms:
                    try:
                        task_queue.enqueue(
                            publish_scheduled_post, sched.id, platform_name
                        )
                    except Exception:
                        logger.exception(
                            "Failed to enqueue publish job for schedule %d (%s)",
                            sched.id, platform_name,
                        )
            logger.info(
                "Dispatched %d schedule(s) for execution", len(claimed)
            )
        else:
            for sched in claimed:
                for platform_name in sched.platforms:
                    try:
                        publish_scheduled_post(sched.id, platform_name)
                    except Exception:
                        logger.exception(
                            "Inline publish failed for schedule %d (%s)",
                            sched.id, platform_name,
                        )


def _dispatch_comment_fetches(app):
    """Called every 5 minutes — enqueue (or run inline) comment fetches."""
    with app.app_context():
        from socialposter.core import queue as task_queue
        from socialposter.core.jobs import fetch_post_comments
        from socialposter.web.models import PublishedPost

        cutoff = datetime.now(timezone.utc) - COMMENT_FETCH_COOLDOWN
        posts = PublishedPost.query.filter(
            (PublishedPost.last_comment_fetch == None)  # noqa: E711
            | (PublishedPost.last_comment_fetch <= cutoff)
        ).all()

        if not posts:
            return

        if task_queue.is_enabled():
            for post in posts:
                try:
                    task_queue.enqueue(fetch_post_comments, post.id)
                except Exception:
                    logger.exception(
                        "Failed to enqueue comment fetch for post %d", post.id
                    )
        else:
            for post in posts:
                try:
                    fetch_post_comments(post.id)
                except Exception:
                    logger.exception(
                        "Inline comment fetch failed for post %d", post.id
                    )


def _dispatch_engagement_fetches(app):
    """Called every 30 minutes — enqueue (or run inline) engagement fetches."""
    with app.app_context():
        from socialposter.core import queue as task_queue
        from socialposter.core.jobs import fetch_post_engagement
        from socialposter.web.models import PublishedPost

        posts = PublishedPost.query.all()
        if not posts:
            return

        if task_queue.is_enabled():
            for post in posts:
                try:
                    task_queue.enqueue(fetch_post_engagement, post.id)
                except Exception:
                    logger.exception(
                        "Failed to enqueue engagement fetch for post %d", post.id
                    )
        else:
            for post in posts:
                try:
                    fetch_post_engagement(post.id)
                except Exception:
                    logger.exception(
                        "Inline engagement fetch failed for post %d", post.id
                    )


def init_scheduler(app):
    """Start the APScheduler background job. Called from create_app()."""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _execute_due_posts, "interval", seconds=30, args=[app], id="due_posts_check"
    )
    scheduler.add_job(
        _dispatch_comment_fetches, "interval", minutes=5, args=[app], id="comment_fetch",
    )
    scheduler.add_job(
        _dispatch_engagement_fetches, "interval", minutes=30, args=[app], id="engagement_fetch",
    )

    from socialposter.core.automation_engine import evaluate_rules
    scheduler.add_job(
        evaluate_rules, "interval", minutes=10, args=[app], id="automation_rules"
    )

    scheduler.start()

    from socialposter.core import queue as task_queue
    backend = "queue" if task_queue.is_enabled() else "inline"
    logger.info(
        "Background scheduler started (backend=%s, 30s posts / 5min comments / 30min engagement / 10min automation)",
        backend,
    )
