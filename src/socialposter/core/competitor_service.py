"""Competitor analysis service — fetches posts and generates AI insights."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("socialposter")


def fetch_competitor_posts(app, competitor_id: int) -> int:
    """Fetch recent public posts for a single competitor. Return count of new posts."""
    with app.app_context():
        from socialposter.web.models import CompetitorAccount, CompetitorPost, db
        from socialposter.platforms.registry import PlatformRegistry

        competitor = db.session.get(CompetitorAccount, competitor_id)
        if not competitor or not competitor.is_active:
            return 0

        registry = PlatformRegistry.all()
        platform_cls = registry.get(competitor.platform)
        if not platform_cls:
            logger.warning("No platform plugin for %s", competitor.platform)
            return 0

        instance = platform_cls()
        if not hasattr(instance, "fetch_public_posts"):
            logger.info("Platform %s does not support public post fetching", competitor.platform)
            return 0

        try:
            raw_posts = instance.fetch_public_posts(
                competitor.user_id, competitor.handle, count=20
            )
        except Exception:
            logger.exception("Failed to fetch posts for competitor %d", competitor_id)
            return 0

        new_count = 0
        for p in raw_posts:
            existing = CompetitorPost.query.filter_by(
                competitor_id=competitor.id,
                platform_post_id=p.get("post_id", ""),
            ).first()
            if existing:
                # Update engagement numbers
                existing.likes = p.get("likes", existing.likes)
                existing.comments = p.get("comments", existing.comments)
                existing.shares = p.get("shares", existing.shares)
                existing.views = p.get("views", existing.views)
            else:
                cp = CompetitorPost(
                    competitor_id=competitor.id,
                    platform_post_id=p.get("post_id", ""),
                    text=p.get("text", ""),
                    likes=p.get("likes", 0),
                    comments=p.get("comments", 0),
                    shares=p.get("shares", 0),
                    views=p.get("views", 0),
                    posted_at=p.get("posted_at"),
                )
                db.session.add(cp)
                new_count += 1

        competitor.last_fetched_at = datetime.now(timezone.utc)
        db.session.commit()
        return new_count


def fetch_all_competitors(app) -> None:
    """Background job entry point — fetch posts for all active competitors."""
    with app.app_context():
        from socialposter.web.models import CompetitorAccount

        competitors = CompetitorAccount.query.filter_by(is_active=True).all()
        for comp in competitors:
            try:
                count = fetch_competitor_posts(app, comp.id)
                if count:
                    logger.info("Fetched %d new posts for competitor %d (%s)",
                                count, comp.id, comp.handle)
            except Exception:
                logger.exception("Failed competitor fetch for %d", comp.id)


def generate_competitor_analysis(
    user_id: int,
    competitor_ids: list[int],
    period_days: int = 30,
) -> str:
    """Generate AI-powered competitor analysis."""
    from socialposter.web.models import (
        CompetitorAccount, CompetitorPost, CompetitorAnalysis, db,
    )
    from socialposter.core.ai_service import get_provider

    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    # Gather competitor data
    summaries = []
    competitor_names = []
    for cid in competitor_ids:
        comp = db.session.get(CompetitorAccount, cid)
        if not comp or comp.user_id != user_id:
            continue
        competitor_names.append(comp.handle)

        posts = CompetitorPost.query.filter(
            CompetitorPost.competitor_id == cid,
            CompetitorPost.posted_at >= since if CompetitorPost.posted_at is not None else True,
        ).order_by(CompetitorPost.posted_at.desc()).limit(50).all()

        total_likes = sum(p.likes for p in posts)
        total_comments = sum(p.comments for p in posts)
        total_shares = sum(p.shares for p in posts)
        top_posts = sorted(posts, key=lambda p: p.likes + p.comments + p.shares, reverse=True)[:3]

        summary = (
            f"@{comp.handle} ({comp.platform}): "
            f"{len(posts)} posts, {total_likes} likes, "
            f"{total_comments} comments, {total_shares} shares. "
        )
        if top_posts:
            summary += "Top posts: " + "; ".join(
                f'"{p.text[:100]}..." ({p.likes}L/{p.comments}C/{p.shares}S)'
                for p in top_posts
            )
        summaries.append(summary)

    if not summaries:
        return "No competitor data available for analysis."

    # Generate AI analysis
    try:
        provider = get_provider(user_id=user_id)
    except ValueError:
        provider = get_provider()

    system = (
        "You are a social media strategist. Analyze competitor performance data and "
        "provide actionable insights. Include: key trends, content strategies that work, "
        "engagement patterns, and recommendations for outperforming these competitors."
    )
    user_prompt = (
        f"Analyze these competitors' performance over the last {period_days} days:\n\n"
        + "\n\n".join(summaries)
        + "\n\nProvide a concise analysis with actionable recommendations."
    )

    analysis_text = provider.chat(system, user_prompt).strip()

    # Save analysis
    analysis = CompetitorAnalysis(
        user_id=user_id,
        analysis_text=analysis_text,
        competitors=competitor_names,
        period_days=period_days,
    )
    db.session.add(analysis)
    db.session.commit()

    return analysis_text
