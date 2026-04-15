"""Publishing helpers – platform override building and published-post recording."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("socialposter")


def build_platform_overrides(
    platforms: list[str],
    raw_overrides: dict[str, Any],
) -> dict[str, Any]:
    """Build a kwargs dict suitable for ``PlatformOverrides(**result)``.

    Parameters
    ----------
    platforms:
        List of platform name strings (e.g. ``["linkedin", "twitter"]``).
    raw_overrides:
        Raw override dicts keyed by platform name (may be empty).
    """
    from socialposter.core.content import (
        FacebookOverride,
        InstagramOverride,
        LinkedInOverride,
        TwitterOverride,
        WhatsAppOverride,
        YouTubeOverride,
    )

    _BUILDERS: dict[str, Any] = {
        "linkedin": lambda ov: LinkedInOverride(
            enabled=True,
            text=ov.get("text") or None,
            visibility=ov.get("visibility", "public"),
        ),
        "youtube": lambda ov: YouTubeOverride(
            enabled=True,
            title=ov.get("title") or None,
            description=ov.get("description") or None,
            tags=ov.get("tags", []),
            privacy=ov.get("privacy", "public"),
        ),
        "instagram": lambda ov: InstagramOverride(
            enabled=True,
            text=ov.get("text") or None,
            post_type=ov.get("post_type", "feed"),
        ),
        "facebook": lambda ov: FacebookOverride(
            enabled=True,
            text=ov.get("text") or None,
            link=ov.get("link") or None,
        ),
        "twitter": lambda ov: TwitterOverride(
            enabled=True,
            text=ov.get("text") or None,
        ),
        "whatsapp": lambda ov: WhatsAppOverride(
            enabled=True,
            text=ov.get("text") or None,
            recipients=ov.get("recipients", []),
        ),
    }

    kwargs: dict[str, Any] = {}
    for pname in platforms:
        builder = _BUILDERS.get(pname)
        if builder:
            kwargs[pname] = builder(raw_overrides.get(pname, {}))
    return kwargs


def record_published_post(
    user_id: int,
    team_id: int | None,
    result,
    text_preview: str,
) -> None:
    """Create a ``PublishedPost`` row with try/except/rollback.

    Parameters
    ----------
    result:
        A publish result object with ``.platform``, ``.post_id``,
        ``.post_url`` attributes.
    text_preview:
        First ~300 chars of the post text.
    """
    from socialposter.web.models import PublishedPost, db

    try:
        pp = PublishedPost(
            team_id=team_id,
            user_id=user_id,
            platform=result.platform,
            platform_post_id=result.post_id or "",
            platform_post_url=result.post_url or "",
            text_preview=text_preview[:300] if text_preview else "",
        )
        db.session.add(pp)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to record published post")
