"""Abstract base class for all platform plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from socialposter.core.content import PostFile, PostType


@dataclass
class PostResult:
    """Outcome of a publish attempt."""

    success: bool
    platform: str
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None


class BasePlatform(ABC):
    """Every platform plugin must inherit from this class."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Machine-readable identifier, e.g. 'linkedin'."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. 'LinkedIn'."""
        ...

    @property
    @abstractmethod
    def supported_post_types(self) -> list[PostType]:
        """Post types this platform can handle."""
        ...

    @property
    @abstractmethod
    def max_text_length(self) -> Optional[int]:
        """Character limit for text, or None if unlimited."""
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_connection(self, user_id: int):
        """Query PlatformConnection for this user and ensure the token is fresh."""
        from socialposter.web.models import PlatformConnection

        conn = PlatformConnection.query.filter_by(
            user_id=user_id, platform=self.name
        ).first()
        if conn is not None:
            conn.ensure_fresh_token()
        return conn

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def authenticate(self, user_id: int) -> bool:
        """Load / refresh credentials. Return True if ready to publish."""
        ...

    @abstractmethod
    def validate(self, content: PostFile, user_id: int) -> list[str]:
        """Validate content for this platform. Return list of error strings (empty = OK)."""
        ...

    @abstractmethod
    def publish(self, content: PostFile, user_id: int) -> PostResult:
        """Publish content. Return a PostResult."""
        ...

    # ------------------------------------------------------------------
    # Community Management (optional – override in subclasses)
    # ------------------------------------------------------------------

    def supports_comment_fetching(self) -> bool:
        """Return True if this platform supports fetching comments."""
        return False

    def fetch_comments(self, user_id: int, post_id: str, since=None) -> list[dict]:
        """Fetch comments for a published post. Return list of comment dicts."""
        return []

    def reply_to_comment(self, user_id: int, comment_id: str, post_id: str, text: str) -> dict:
        """Reply to a comment. Return {'success': bool, 'error': str}."""
        return {"success": False, "error": "Not implemented"}

    # ------------------------------------------------------------------
    # Engagement Analytics (optional – override in subclasses)
    # ------------------------------------------------------------------

    def supports_engagement_fetching(self) -> bool:
        """Return True if this platform supports fetching engagement metrics."""
        return False

    def fetch_engagement(self, user_id: int, post_id: str) -> dict | None:
        """Fetch engagement metrics for a published post.

        Return dict with keys: likes, comments, shares, views, clicks
        or None if not supported.
        """
        return None

    # ------------------------------------------------------------------
    # Competitor / Public Post Fetching (optional – override in subclasses)
    # ------------------------------------------------------------------

    def supports_public_post_fetching(self) -> bool:
        """Return True if this platform supports fetching public posts by handle."""
        return False

    def fetch_public_posts(self, user_id: int, handle: str, count: int = 20) -> list[dict]:
        """Fetch public posts for a given handle.

        Return list of dicts with keys: post_id, text, likes, comments,
        shares, views, posted_at.
        """
        return []
