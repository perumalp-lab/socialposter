"""LinkedIn platform plugin – Posts API with OAuth 2.0."""

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

API_BASE = "https://api.linkedin.com/v2"


@PlatformRegistry.register
class LinkedInPlatform(BasePlatform):

    @property
    def name(self) -> str:
        return "linkedin"

    @property
    def display_name(self) -> str:
        return "LinkedIn"

    @property
    def supported_post_types(self) -> list[PostType]:
        return [PostType.TEXT, PostType.IMAGE, PostType.VIDEO]

    @property
    def max_text_length(self) -> Optional[int]:
        return PLATFORM_TEXT_LIMITS["linkedin"]

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self, user_id: int) -> bool:
        """Check if we have a valid access token."""
        conn = self._get_connection(user_id)
        if not conn:
            logger.warning("[LinkedIn] No access token configured")
            return False
        try:
            resp = requests.get(
                f"{API_BASE}/userinfo",
                headers={"Authorization": f"Bearer {conn.access_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return True
            logger.warning(f"[LinkedIn] Token validation failed: {resp.status_code}")
            return False
        except requests.RequestException as e:
            logger.warning(f"[LinkedIn] Connection error: {e}")
            return False

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, content: PostFile, user_id: int) -> list[str]:
        errors: list[str] = []
        text = content.get_text("linkedin")
        if not text:
            errors.append("[LinkedIn] Post text is empty")
        elif len(text) > self.max_text_length:
            errors.append(f"[LinkedIn] Text too long: {len(text)}/{self.max_text_length} chars")
        # Validate media
        errors.extend(validate_all_media(content.get_media("linkedin"), "linkedin"))
        return errors

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    @retry(max_attempts=3, base_delay=2.0)
    def publish(self, content: PostFile, user_id: int) -> PostResult:
        conn = self._get_connection(user_id)
        if not conn:
            return PostResult(success=False, platform="linkedin", error_message="No access token")

        token = conn.access_token

        # Get user URN
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            me = requests.get(f"{API_BASE}/userinfo", headers=headers, timeout=10)
            me.raise_for_status()
            user_sub = me.json().get("sub")
            author_urn = f"urn:li:person:{user_sub}"
        except Exception as e:
            return PostResult(success=False, platform="linkedin", error_message=f"Failed to get profile: {e}")

        text = content.get_text("linkedin")

        # Build the post payload (text-only for now; media upload is a multi-step extension)
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        try:
            resp = requests.post(
                f"{API_BASE}/ugcPosts",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                post_id = resp.json().get("id", "")
                return PostResult(
                    success=True,
                    platform="linkedin",
                    post_id=post_id,
                    post_url=f"https://www.linkedin.com/feed/update/{post_id}",
                )
            else:
                return PostResult(
                    success=False,
                    platform="linkedin",
                    error_message=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
        except requests.RequestException as e:
            return PostResult(success=False, platform="linkedin", error_message=str(e))

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
            headers = {"Authorization": f"Bearer {conn.access_token}"}
            urn = post_id if post_id.startswith("urn:") else f"urn:li:share:{post_id}"
            resp = requests.get(
                f"{API_BASE}/socialActions/{urn}/comments",
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                return []
            comments = []
            for c in resp.json().get("elements", []):
                actor = c.get("actor", "")
                comments.append({
                    "comment_id": c.get("$URN", c.get("commentUrn", "")),
                    "author_name": actor,
                    "author_profile_url": f"https://linkedin.com/in/{actor}",
                    "author_avatar_url": "",
                    "text": c.get("message", {}).get("text", ""),
                    "posted_at": None,
                })
            return comments
        except Exception as e:
            logger.warning("[LinkedIn] Failed to fetch comments: %s", e)
            return []

    def reply_to_comment(self, user_id: int, comment_id: str, post_id: str, text: str) -> dict:
        conn = self._get_connection(user_id)
        if not conn:
            return {"success": False, "error": "Not authenticated"}
        try:
            headers = {
                "Authorization": f"Bearer {conn.access_token}",
                "Content-Type": "application/json",
            }
            urn = post_id if post_id.startswith("urn:") else f"urn:li:share:{post_id}"
            me = requests.get(f"{API_BASE}/userinfo", headers=headers, timeout=10)
            me.raise_for_status()
            actor = f"urn:li:person:{me.json().get('sub')}"

            resp = requests.post(
                f"{API_BASE}/socialActions/{urn}/comments",
                headers=headers,
                json={
                    "actor": actor,
                    "message": {"text": text},
                    "parentComment": comment_id,
                },
                timeout=15,
            )
            if resp.status_code in (200, 201):
                return {"success": True}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
