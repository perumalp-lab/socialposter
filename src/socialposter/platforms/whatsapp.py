"""WhatsApp platform plugin – Meta Cloud API for business messaging."""

from __future__ import annotations

from typing import Optional

import requests

from socialposter.core.content import PLATFORM_TEXT_LIMITS, PostFile, PostType
from socialposter.platforms.base import BasePlatform, PostResult
from socialposter.platforms.registry import PlatformRegistry
from socialposter.utils.logger import get_logger
from socialposter.utils.retry import retry

logger = get_logger()

GRAPH_API = "https://graph.facebook.com/v19.0"


@PlatformRegistry.register
class WhatsAppPlatform(BasePlatform):

    @property
    def name(self) -> str:
        return "whatsapp"

    @property
    def display_name(self) -> str:
        return "WhatsApp"

    @property
    def supported_post_types(self) -> list[PostType]:
        return [PostType.TEXT, PostType.IMAGE, PostType.VIDEO]

    @property
    def max_text_length(self) -> Optional[int]:
        return PLATFORM_TEXT_LIMITS["whatsapp"]

    def _get_phone_number_id(self, user_id: int) -> Optional[str]:
        conn = self._get_connection(user_id)
        if conn and conn.extra_data:
            return conn.extra_data.get("phone_number_id")
        return None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self, user_id: int) -> bool:
        conn = self._get_connection(user_id)
        phone_id = self._get_phone_number_id(user_id)
        if not conn or not phone_id:
            logger.warning("[WhatsApp] Missing access token or phone_number_id")
            return False
        try:
            resp = requests.get(
                f"{GRAPH_API}/{phone_id}",
                headers={"Authorization": f"Bearer {conn.access_token}"},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.warning("[WhatsApp] Auth check failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, content: PostFile, user_id: int) -> list[str]:
        errors: list[str] = []
        override = content.platforms.whatsapp
        if not override:
            errors.append("[WhatsApp] No whatsapp config in content file")
            return errors

        if not override.recipients:
            errors.append("[WhatsApp] No recipients specified")

        # Either template, override text, or default text must be provided
        effective_text = override.text or content.get_text("whatsapp")
        if not override.template_name and not effective_text:
            errors.append("[WhatsApp] Either template_name or text is required")

        if effective_text and len(effective_text) > self.max_text_length:
            errors.append(f"[WhatsApp] Text too long: {len(effective_text)}/{self.max_text_length}")

        return errors

    # ------------------------------------------------------------------
    # Publish (send messages to recipients)
    # ------------------------------------------------------------------

    @retry(max_attempts=2, base_delay=2.0)
    def publish(self, content: PostFile, user_id: int) -> PostResult:
        conn = self._get_connection(user_id)
        phone_id = self._get_phone_number_id(user_id)
        if not conn or not phone_id:
            return PostResult(success=False, platform="whatsapp", error_message="Not authenticated")

        token = conn.access_token
        override = content.platforms.whatsapp
        if not override:
            return PostResult(success=False, platform="whatsapp", error_message="No config")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        endpoint = f"{GRAPH_API}/{phone_id}/messages"

        sent = 0
        errors_list: list[str] = []

        for recipient in override.recipients:
            if override.template_name:
                # Template message
                payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "template",
                    "template": {
                        "name": override.template_name,
                        "language": {"code": override.template_language},
                    },
                }
                # Add template parameters if provided
                if override.template_params:
                    payload["template"]["components"] = [{
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in override.template_params],
                    }]
            else:
                # Free-form text (only works within 24h service window)
                payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": override.text or content.get_text("whatsapp")},
                }

            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    sent += 1
                else:
                    errors_list.append(f"{recipient}: HTTP {resp.status_code}")
            except Exception as e:
                errors_list.append(f"{recipient}: {e}")

        if sent == len(override.recipients):
            return PostResult(
                success=True,
                platform="whatsapp",
                post_id=f"{sent}_messages_sent",
            )
        elif sent > 0:
            return PostResult(
                success=True,
                platform="whatsapp",
                post_id=f"{sent}/{len(override.recipients)}_sent",
                error_message=f"Partial: {'; '.join(errors_list)}",
            )
        else:
            return PostResult(
                success=False,
                platform="whatsapp",
                error_message=f"All failed: {'; '.join(errors_list)}",
            )

    # WhatsApp does not support comment fetching (requires webhooks)
    def supports_comment_fetching(self) -> bool:
        return False
