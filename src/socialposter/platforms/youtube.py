"""YouTube platform plugin – Data API v3 for video uploads."""

from __future__ import annotations

from typing import Optional

from socialposter.core.content import PLATFORM_TEXT_LIMITS, PostFile, PostType
from socialposter.core.media import validate_all_media
from socialposter.platforms.base import BasePlatform, PostResult
from socialposter.platforms.registry import PlatformRegistry
from socialposter.web.models import AppSetting
from socialposter.utils.logger import get_logger
from socialposter.utils.retry import retry

logger = get_logger()

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


@PlatformRegistry.register
class YouTubePlatform(BasePlatform):

    @property
    def name(self) -> str:
        return "youtube"

    @property
    def display_name(self) -> str:
        return "YouTube"

    @property
    def supported_post_types(self) -> list[PostType]:
        return [PostType.VIDEO]

    @property
    def max_text_length(self) -> Optional[int]:
        return PLATFORM_TEXT_LIMITS["youtube"]

    def _get_credentials(self, user_id: int):
        """Build Google OAuth credentials from DB-stored tokens."""
        from google.oauth2.credentials import Credentials

        conn = self._get_connection(user_id)
        if not conn or not conn.refresh_token:
            return None

        client_id = AppSetting.get("google_client_id")
        client_secret = AppSetting.get("google_client_secret")

        creds = Credentials(
            token=conn.access_token,
            refresh_token=conn.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id or "",
            client_secret=client_secret or "",
            scopes=SCOPES,
        )
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        return creds

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self, user_id: int) -> bool:
        try:
            creds = self._get_credentials(user_id)
            return creds is not None and creds.valid
        except Exception as e:
            logger.warning(f"[YouTube] Auth failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, content: PostFile, user_id: int) -> list[str]:
        errors: list[str] = []
        override = content.platforms.youtube
        if not override:
            errors.append("[YouTube] No youtube config in content file")
            return errors

        if not override.title:
            errors.append("[YouTube] Video title is required")

        media = content.get_media("youtube")
        video_found = any(m.media_type.value == "video" for m in media)
        if not video_found:
            errors.append("[YouTube] At least one video file is required")

        errors.extend(validate_all_media(media, "youtube"))
        return errors

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    @retry(max_attempts=2, base_delay=5.0)
    def publish(self, content: PostFile, user_id: int) -> PostResult:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = self._get_credentials(user_id)
        if not creds:
            return PostResult(success=False, platform="youtube", error_message="Not authenticated")

        override = content.platforms.youtube
        media = content.get_media("youtube")

        # Find the video file
        video_file = next((m for m in media if m.media_type.value == "video"), None)
        if not video_file or video_file.path.startswith("http"):
            return PostResult(success=False, platform="youtube", error_message="Local video file required")

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": override.title or "Untitled",
                "description": override.description or content.get_text("youtube"),
                "tags": override.tags,
                "categoryId": str(override.category_id),
            },
            "status": {
                "privacyStatus": override.privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media_upload = MediaFileUpload(
            video_file.path,
            mimetype="video/*",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        try:
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media_upload)
            response = None
            while response is None:
                _, response = request.next_chunk()

            video_id = response.get("id", "")

            # Upload thumbnail if provided
            thumbnail = next((m for m in media if m.media_type.value == "thumbnail"), None)
            if thumbnail and not thumbnail.path.startswith("http"):
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail.path, mimetype="image/jpeg"),
                ).execute()

            return PostResult(
                success=True,
                platform="youtube",
                post_id=video_id,
                post_url=f"https://youtube.com/watch?v={video_id}",
            )
        except Exception as e:
            return PostResult(success=False, platform="youtube", error_message=str(e))

    # ------------------------------------------------------------------
    # Community Management
    # ------------------------------------------------------------------

    def supports_comment_fetching(self) -> bool:
        return True

    def fetch_comments(self, user_id: int, post_id: str, since=None) -> list[dict]:
        try:
            from googleapiclient.discovery import build
            creds = self._get_credentials(user_id)
            if not creds:
                return []
            youtube = build("youtube", "v3", credentials=creds)
            resp = youtube.commentThreads().list(
                part="snippet", videoId=post_id, maxResults=50, order="time"
            ).execute()
            comments = []
            for item in resp.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "comment_id": item["snippet"]["topLevelComment"]["id"],
                    "author_name": snippet.get("authorDisplayName", ""),
                    "author_profile_url": snippet.get("authorChannelUrl", ""),
                    "author_avatar_url": snippet.get("authorProfileImageUrl", ""),
                    "text": snippet.get("textDisplay", ""),
                    "posted_at": snippet.get("publishedAt"),
                })
            return comments
        except Exception as e:
            logger.warning("[YouTube] Failed to fetch comments: %s", e)
            return []

    def reply_to_comment(self, user_id: int, comment_id: str, post_id: str, text: str) -> dict:
        try:
            from googleapiclient.discovery import build
            creds = self._get_credentials(user_id)
            if not creds:
                return {"success": False, "error": "Not authenticated"}
            youtube = build("youtube", "v3", credentials=creds)
            youtube.comments().insert(
                part="snippet",
                body={
                    "snippet": {
                        "parentId": comment_id,
                        "textOriginal": text,
                    }
                },
            ).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
