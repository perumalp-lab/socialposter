"""Instagram platform plugin – Meta Graph API for Business accounts."""

from __future__ import annotations

from typing import Optional

import requests

from socialposter.core.content import PLATFORM_TEXT_LIMITS, PostFile, PostType
from socialposter.core.media import validate_all_media
from socialposter.platforms.base import BasePlatform, PostResult
from socialposter.platforms.registry import PlatformRegistry
from socialposter.utils.logger import get_logger
from socialposter.utils.retry import retry

logger = get_logger()

GRAPH_API = "https://graph.facebook.com/v19.0"


@PlatformRegistry.register
class InstagramPlatform(BasePlatform):

    @property
    def name(self) -> str:
        return "instagram"

    @property
    def display_name(self) -> str:
        return "Instagram"

    @property
    def supported_post_types(self) -> list[PostType]:
        return [PostType.IMAGE, PostType.VIDEO, PostType.CAROUSEL, PostType.REEL, PostType.STORY]

    @property
    def max_text_length(self) -> Optional[int]:
        return PLATFORM_TEXT_LIMITS["instagram"]

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_ig_account_id(self, user_id: int) -> Optional[str]:
        """Return the Instagram Business Account ID from the database."""
        conn = self._get_connection(user_id)
        if conn and conn.extra_data:
            return conn.extra_data.get("business_account_id")
        return None

    def authenticate(self, user_id: int) -> bool:
        conn = self._get_connection(user_id)
        if not conn:
            logger.warning("[Instagram] No access token configured")
            return False
        ig_id = self._get_ig_account_id(user_id)
        if not ig_id:
            logger.warning("[Instagram] No business_account_id configured")
            return False
        try:
            resp = requests.get(
                f"{GRAPH_API}/{ig_id}",
                params={"fields": "id,username", "access_token": conn.access_token},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.warning("[Instagram] Auth check failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, content: PostFile, user_id: int) -> list[str]:
        errors: list[str] = []
        text = content.get_text("instagram")
        if text and len(text) > self.max_text_length:
            errors.append(f"[Instagram] Caption too long: {len(text)}/{self.max_text_length} chars")

        media = content.get_media("instagram")
        if not media:
            errors.append("[Instagram] At least one media item is required (Instagram doesn't support text-only)")

        # Instagram Graph API requires media at a public URL
        for item in media:
            if not item.path.startswith("http"):
                errors.append(
                    f"[Instagram] Media must be a public URL (not a local file): {item.path}. "
                    "Upload to a hosting service first."
                )

        errors.extend(validate_all_media(media, "instagram"))
        return errors

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    @retry(max_attempts=3, base_delay=3.0)
    def publish(self, content: PostFile, user_id: int) -> PostResult:
        conn = self._get_connection(user_id)
        ig_id = self._get_ig_account_id(user_id)
        if not conn or not ig_id:
            return PostResult(success=False, platform="instagram", error_message="Not authenticated")

        token = conn.access_token
        text = content.get_text("instagram")
        media = content.get_media("instagram")
        override = content.platforms.instagram
        post_type = override.post_type if override else "feed"

        if not media:
            return PostResult(success=False, platform="instagram", error_message="No media provided")

        try:
            # Step 1: Create media container
            item = media[0]
            container_data = {"access_token": token, "caption": text}

            if post_type == "reel" and item.media_type.value == "video":
                container_data["media_type"] = "REELS"
                container_data["video_url"] = item.path
            elif item.media_type.value == "image":
                container_data["image_url"] = item.path
            elif item.media_type.value == "video":
                container_data["media_type"] = "VIDEO"
                container_data["video_url"] = item.path

            resp = requests.post(
                f"{GRAPH_API}/{ig_id}/media",
                data=container_data,
                timeout=30,
            )
            if resp.status_code != 200:
                return PostResult(success=False, platform="instagram",
                                  error_message=f"Container creation failed: {resp.text[:300]}")

            container_id = resp.json().get("id")

            # Step 2: Publish the container
            pub_resp = requests.post(
                f"{GRAPH_API}/{ig_id}/media_publish",
                data={"creation_id": container_id, "access_token": token},
                timeout=60,
            )
            if pub_resp.status_code == 200:
                post_id = pub_resp.json().get("id", "")
                return PostResult(
                    success=True,
                    platform="instagram",
                    post_id=post_id,
                    post_url=f"https://instagram.com/p/{post_id}",
                )
            else:
                return PostResult(success=False, platform="instagram",
                                  error_message=f"Publish failed: {pub_resp.text[:300]}")

        except Exception as e:
            return PostResult(success=False, platform="instagram", error_message=str(e))

    # ------------------------------------------------------------------
    # Community Management
    # ------------------------------------------------------------------

    def supports_comment_fetching(self) -> bool:
        return True

    def fetch_comments(self, user_id: int, post_id: str, since=None) -> list[dict]:
        conn = self._get_connection(user_id)
        if not conn:
            return []
        try:
            params = {"access_token": conn.access_token, "fields": "id,text,username,timestamp"}
            resp = requests.get(f"{GRAPH_API}/{post_id}/comments", params=params, timeout=15)
            if resp.status_code != 200:
                return []
            comments = []
            for c in resp.json().get("data", []):
                comments.append({
                    "comment_id": c.get("id", ""),
                    "author_name": c.get("username", ""),
                    "author_profile_url": f"https://instagram.com/{c.get('username', '')}",
                    "author_avatar_url": "",
                    "text": c.get("text", ""),
                    "posted_at": c.get("timestamp"),
                })
            return comments
        except Exception as e:
            logger.warning("[Instagram] Failed to fetch comments: %s", e)
            return []

    def reply_to_comment(self, user_id: int, comment_id: str, post_id: str, text: str) -> dict:
        conn = self._get_connection(user_id)
        if not conn:
            return {"success": False, "error": "Not authenticated"}
        try:
            resp = requests.post(
                f"{GRAPH_API}/{comment_id}/replies",
                data={"message": text, "access_token": conn.access_token},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"success": True}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
