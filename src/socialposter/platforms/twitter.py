"""X (Twitter) platform plugin – API v2 via tweepy."""

from __future__ import annotations

from typing import Optional

from socialposter.core.content import PLATFORM_TEXT_LIMITS, PostFile, PostType
from socialposter.core.media import validate_all_media
from socialposter.platforms.base import BasePlatform, PostResult
from socialposter.platforms.registry import PlatformRegistry
from socialposter.utils.logger import get_logger
from socialposter.utils.retry import retry

logger = get_logger()


@PlatformRegistry.register
class TwitterPlatform(BasePlatform):

    @property
    def name(self) -> str:
        return "twitter"

    @property
    def display_name(self) -> str:
        return "X (Twitter)"

    @property
    def supported_post_types(self) -> list[PostType]:
        return [PostType.TEXT, PostType.IMAGE, PostType.VIDEO, PostType.THREAD]

    @property
    def max_text_length(self) -> Optional[int]:
        return PLATFORM_TEXT_LIMITS["twitter"]

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_client(self, user_id: int):
        """Return an authenticated tweepy Client using OAuth 2.0."""
        import tweepy

        conn = self._get_connection(user_id)
        if not conn:
            return None
        return tweepy.Client(bearer_token=conn.access_token)

    def authenticate(self, user_id: int) -> bool:
        client = self._get_client(user_id)
        if client is None:
            logger.warning("[Twitter] No access token configured")
            return False
        try:
            me = client.get_me()
            return me.data is not None
        except Exception as e:
            logger.warning("[Twitter] Auth check failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, content: PostFile, user_id: int) -> list[str]:
        errors: list[str] = []
        text = content.get_text("twitter")
        if not text:
            errors.append("[Twitter] Post text is empty")
        elif len(text) > self.max_text_length:
            errors.append(f"[Twitter] Text too long: {len(text)}/{self.max_text_length} chars")
        errors.extend(validate_all_media(content.get_media("twitter"), "twitter"))
        return errors

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    @retry(max_attempts=2, base_delay=3.0)
    def publish(self, content: PostFile, user_id: int) -> PostResult:
        client = self._get_client(user_id)
        if client is None:
            return PostResult(success=False, platform="twitter", error_message="Not authenticated")

        text = content.get_text("twitter")

        try:
            response = client.create_tweet(text=text)
            tweet_id = response.data.get("id")

            # Handle thread if defined
            override = content.platforms.twitter
            if override and override.thread:
                parent_id = tweet_id
                for thread_text in override.thread:
                    resp = client.create_tweet(text=thread_text, in_reply_to_tweet_id=parent_id)
                    parent_id = resp.data.get("id")

            return PostResult(
                success=True,
                platform="twitter",
                post_id=tweet_id,
                post_url=f"https://x.com/i/status/{tweet_id}",
            )
        except Exception as e:
            return PostResult(success=False, platform="twitter", error_message=str(e))

    # ------------------------------------------------------------------
    # Community Management
    # ------------------------------------------------------------------

    def supports_comment_fetching(self) -> bool:
        return True

    def fetch_comments(self, user_id: int, post_id: str, since=None) -> list[dict]:
        try:
            import tweepy
            conn = self._get_connection(user_id)
            if not conn:
                return []
            client = tweepy.Client(bearer_token=conn.access_token)
            # Search for mentions/replies to the tweet
            me = client.get_me()
            if not me.data:
                return []
            mentions = client.get_users_mentions(
                me.data.id, max_results=50,
                tweet_fields=["author_id", "created_at", "in_reply_to_user_id"],
            )
            comments = []
            if mentions.data:
                for tweet in mentions.data:
                    comments.append({
                        "comment_id": str(tweet.id),
                        "author_name": str(tweet.author_id),
                        "author_profile_url": f"https://x.com/i/user/{tweet.author_id}",
                        "author_avatar_url": "",
                        "text": tweet.text,
                        "posted_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    })
            return comments
        except Exception as e:
            logger.warning("[Twitter] Failed to fetch comments: %s", e)
            return []

    def reply_to_comment(self, user_id: int, comment_id: str, post_id: str, text: str) -> dict:
        try:
            client = self._get_client(user_id)
            if not client:
                return {"success": False, "error": "Not authenticated"}
            client.create_tweet(text=text, in_reply_to_tweet_id=comment_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Competitor / Public Post Fetching
    # ------------------------------------------------------------------

    def supports_public_post_fetching(self) -> bool:
        return True

    def fetch_public_posts(self, user_id: int, handle: str, count: int = 20) -> list[dict]:
        """Fetch public tweets by handle using the user's bearer token."""
        try:
            import tweepy
            conn = self._get_connection(user_id)
            if not conn:
                return []
            client = tweepy.Client(bearer_token=conn.access_token)

            # Look up user by username
            user_resp = client.get_user(username=handle)
            if not user_resp.data:
                return []

            target_id = user_resp.data.id
            tweets = client.get_users_tweets(
                target_id,
                max_results=min(count, 100),
                tweet_fields=["created_at", "public_metrics"],
            )

            results = []
            if tweets.data:
                for tweet in tweets.data:
                    metrics = tweet.public_metrics or {}
                    results.append({
                        "post_id": str(tweet.id),
                        "text": tweet.text,
                        "likes": metrics.get("like_count", 0),
                        "comments": metrics.get("reply_count", 0),
                        "shares": metrics.get("retweet_count", 0),
                        "views": metrics.get("impression_count", 0),
                        "posted_at": tweet.created_at,
                    })
            return results
        except Exception as e:
            logger.warning("[Twitter] Failed to fetch public posts for %s: %s", handle, e)
            return []
