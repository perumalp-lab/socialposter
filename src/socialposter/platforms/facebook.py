"""Facebook platform plugin – Graph API for Page posts."""

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
class FacebookPlatform(BasePlatform):

    @property
    def name(self) -> str:
        return "facebook"

    @property
    def display_name(self) -> str:
        return "Facebook"

    @property
    def supported_post_types(self) -> list[PostType]:
        return [PostType.TEXT, PostType.IMAGE, PostType.VIDEO]

    @property
    def max_text_length(self) -> Optional[int]:
        return PLATFORM_TEXT_LIMITS["facebook"]

    def _get_page_id(self, user_id: int, override_page_id: Optional[str] = None) -> Optional[str]:
        """Return page_id from content override or PlatformConnection.extra_data."""
        if override_page_id:
            return override_page_id
        conn = self._get_connection(user_id)
        if conn and conn.extra_data:
            return conn.extra_data.get("page_id")
        return None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self, user_id: int) -> bool:
        conn = self._get_connection(user_id)
        if not conn:
            logger.warning("[Facebook] No page access token configured")
            return False
        try:
            resp = requests.get(
                f"{GRAPH_API}/me",
                params={"access_token": conn.access_token},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.warning("[Facebook] Auth check failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, content: PostFile, user_id: int) -> list[str]:
        errors: list[str] = []
        text = content.get_text("facebook")
        if not text:
            errors.append("[Facebook] Post text is empty")
        elif len(text) > self.max_text_length:
            errors.append(f"[Facebook] Text too long: {len(text)}/{self.max_text_length} chars")

        # Check page_id
        override = content.platforms.facebook
        page_id = self._get_page_id(user_id, override.page_id if override else None)
        if not page_id:
            errors.append("[Facebook] No page_id configured. Set it in Connections settings.")

        errors.extend(validate_all_media(content.get_media("facebook"), "facebook"))
        return errors

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    @retry(max_attempts=3, base_delay=2.0)
    def publish(self, content: PostFile, user_id: int) -> PostResult:
        conn = self._get_connection(user_id)
        if not conn:
            return PostResult(success=False, platform="facebook", error_message="No access token")

        token = conn.access_token
        override = content.platforms.facebook
        page_id = self._get_page_id(user_id, override.page_id if override else None)

        text = content.get_text("facebook")
        media = content.get_media("facebook")
        link = override.link if override else None

        try:
            if media and media[0].media_type.value == "image":
                # Photo post
                endpoint = f"{GRAPH_API}/{page_id}/photos"
                files = {}
                data = {"caption": text, "access_token": token}
                if not media[0].path.startswith("http"):
                    files = {"source": open(media[0].path, "rb")}
                else:
                    data["url"] = media[0].path
                resp = requests.post(endpoint, data=data, files=files, timeout=60)
            else:
                # Text/link post
                endpoint = f"{GRAPH_API}/{page_id}/feed"
                data = {"message": text, "access_token": token}
                if link:
                    data["link"] = link
                resp = requests.post(endpoint, data=data, timeout=30)

            if resp.status_code == 200:
                post_id = resp.json().get("id", resp.json().get("post_id", ""))
                return PostResult(
                    success=True,
                    platform="facebook",
                    post_id=post_id,
                    post_url=f"https://facebook.com/{post_id}",
                )
            else:
                return PostResult(
                    success=False,
                    platform="facebook",
                    error_message=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
        except Exception as e:
            return PostResult(success=False, platform="facebook", error_message=str(e))

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
            params = {"access_token": conn.access_token, "fields": "id,from,message,created_time"}
            resp = requests.get(f"{GRAPH_API}/{post_id}/comments", params=params, timeout=15)
            if resp.status_code != 200:
                return []
            comments = []
            for c in resp.json().get("data", []):
                from_info = c.get("from", {})
                comments.append({
                    "comment_id": c.get("id", ""),
                    "author_name": from_info.get("name", ""),
                    "author_profile_url": f"https://facebook.com/{from_info.get('id', '')}",
                    "author_avatar_url": "",
                    "text": c.get("message", ""),
                    "posted_at": c.get("created_time"),
                })
            return comments
        except Exception as e:
            logger.warning("[Facebook] Failed to fetch comments: %s", e)
            return []

    def reply_to_comment(self, user_id: int, comment_id: str, post_id: str, text: str) -> dict:
        conn = self._get_connection(user_id)
        if not conn:
            return {"success": False, "error": "Not authenticated"}
        try:
            resp = requests.post(
                f"{GRAPH_API}/{comment_id}/comments",
                data={"message": text, "access_token": conn.access_token},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"success": True}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
