"""Background scheduler – executes due ScheduledPost rows on a recurring basis."""

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
from socialposter.core.publisher import _publish_one, _resolve_platforms

logger = logging.getLogger("socialposter")


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


def _execute_due_posts(app):
    """Called by APScheduler every 30 seconds inside the Flask app context."""
    with app.app_context():
        from socialposter.web.models import ScheduledPost, ScheduleLog, db

        now = datetime.now(timezone.utc)
        due = ScheduledPost.query.filter(
            ScheduledPost.enabled == True,  # noqa: E712
            ScheduledPost.next_run_at <= now,
        ).all()

        for sched in due:
            try:
                content = _build_post_file(sched)
                platforms = _resolve_platforms(content, sched.platforms)

                results = []
                for platform in platforms:
                    try:
                        result = _publish_one(platform, content, dry_run=False, user_id=sched.user_id)
                        results.append({
                            "platform": result.platform,
                            "success": result.success,
                            "post_id": result.post_id,
                            "post_url": result.post_url,
                            "error": result.error_message,
                        })
                        # Record post history
                        from socialposter.web.models import record_post_history, PublishedPost, TeamMember
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
                        # Dispatch webhook event
                        try:
                            from socialposter.core.webhook_dispatcher import dispatch_event
                            evt = "post.published" if result.success else "post.failed"
                            dispatch_event(app, evt, {
                                "platform": result.platform,
                                "post_id": result.post_id,
                                "post_url": result.post_url,
                                "text": sched.text[:300] if sched.text else "",
                                "error": result.error_message,
                            }, user_id=sched.user_id)
                        except Exception:
                            logger.debug("Webhook dispatch failed", exc_info=True)
                        # Track published post for inbox
                        if result.success and result.post_id:
                            try:
                                tm = TeamMember.query.filter_by(user_id=sched.user_id).first()
                                pp = PublishedPost(
                                    team_id=tm.team_id if tm else None,
                                    user_id=sched.user_id,
                                    platform=result.platform,
                                    platform_post_id=result.post_id or "",
                                    platform_post_url=result.post_url or "",
                                    text_preview=sched.text[:300] if sched.text else "",
                                )
                                db.session.add(pp)
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                    except Exception as e:
                        results.append({
                            "platform": platform.name,
                            "success": False,
                            "post_id": None,
                            "post_url": None,
                            "error": str(e),
                        })

                db.session.add(ScheduleLog(schedule_id=sched.id, results=results))
                sched.next_run_at = now + timedelta(minutes=sched.interval_minutes)
                db.session.commit()
                logger.info("Executed schedule %d (%s)", sched.id, sched.name)
            except Exception:
                db.session.rollback()
                logger.exception("Failed to execute schedule %d", sched.id)


def _fetch_comments(app):
    """Called by APScheduler every 5 minutes to fetch new comments from platforms."""
    with app.app_context():
        from socialposter.web.models import PublishedPost, InboxComment, TeamMember, db
        from socialposter.platforms.registry import PlatformRegistry

        now = datetime.now(timezone.utc)
        posts = PublishedPost.query.all()

        for post in posts:
            try:
                registry = PlatformRegistry.all()
                platform_cls = registry.get(post.platform)
                if not platform_cls:
                    continue
                platform_instance = platform_cls()
                if not platform_instance.supports_comment_fetching():
                    continue

                since = post.last_comment_fetch
                comments = platform_instance.fetch_comments(
                    post.user_id, post.platform_post_id, since=since
                )

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

                # Dispatch webhook for new comments
                if comments:
                    try:
                        from socialposter.core.webhook_dispatcher import dispatch_event
                        dispatch_event(app, "comment.received", {
                            "platform": post.platform,
                            "post_id": post.platform_post_id,
                            "comment_count": len(comments),
                        }, user_id=post.user_id)
                    except Exception:
                        logger.debug("Webhook dispatch failed", exc_info=True)

                post.last_comment_fetch = now
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.exception(
                    "Failed to fetch comments for post %d (%s)", post.id, post.platform
                )


def _fetch_engagement_metrics(app):
    """Called by APScheduler every 30 minutes to fetch engagement metrics."""
    with app.app_context():
        from socialposter.web.models import PublishedPost, EngagementMetric, db
        from socialposter.platforms.registry import PlatformRegistry

        posts = PublishedPost.query.all()

        for post in posts:
            try:
                registry = PlatformRegistry.all()
                platform_cls = registry.get(post.platform)
                if not platform_cls:
                    continue
                platform_instance = platform_cls()
                if not platform_instance.supports_engagement_fetching():
                    continue

                metrics = platform_instance.fetch_engagement(
                    post.user_id, post.platform_post_id
                )
                if not metrics:
                    continue

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
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.exception(
                    "Failed to fetch engagement for post %d (%s)",
                    post.id, post.platform,
                )


def init_scheduler(app):
    """Start the APScheduler background job. Called from create_app()."""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _execute_due_posts, "interval", seconds=30, args=[app], id="due_posts_check"
    )
    scheduler.add_job(
        _fetch_comments, "interval", minutes=5, args=[app], id="comment_fetch"
    )
    scheduler.add_job(
        _fetch_engagement_metrics, "interval", minutes=30, args=[app], id="engagement_fetch"
    )

    from socialposter.core.automation_engine import evaluate_rules
    scheduler.add_job(
        evaluate_rules, "interval", minutes=10, args=[app], id="automation_rules"
    )

    from socialposter.core.competitor_service import fetch_all_competitors
    scheduler.add_job(
        fetch_all_competitors, "interval", hours=2, args=[app], id="competitor_fetch"
    )

    scheduler.start()
    logger.info("Background scheduler started (30s posts, 5min comments, 30min engagement, 10min automation, 2h competitors)")
