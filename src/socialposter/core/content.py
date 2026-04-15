"""Content models and YAML/JSON parser for post definitions."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    THUMBNAIL = "thumbnail"
    DOCUMENT = "document"


class PostType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    REEL = "reel"
    STORY = "story"
    THREAD = "thread"


# ---------------------------------------------------------------------------
# Media Model
# ---------------------------------------------------------------------------

class MediaItem(BaseModel):
    """A single media attachment."""

    path: str = Field(..., description="Local file path or public URL")
    media_type: MediaType = Field(alias="type")
    alt_text: Optional[str] = None
    url: Optional[str] = None  # populated at runtime for platforms needing hosted URLs

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Platform-specific override models
# ---------------------------------------------------------------------------

class LinkedInOverride(BaseModel):
    enabled: bool = True
    text: Optional[str] = None
    visibility: str = "public"
    media: Optional[list[MediaItem]] = None


class YouTubeOverride(BaseModel):
    enabled: bool = True
    title: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    category_id: int = 28  # Science & Technology
    privacy: str = "public"
    media: Optional[list[MediaItem]] = None


class InstagramOverride(BaseModel):
    enabled: bool = True
    text: Optional[str] = None
    media: Optional[list[MediaItem]] = None
    post_type: str = "feed"


class FacebookOverride(BaseModel):
    enabled: bool = True
    page_id: Optional[str] = None
    text: Optional[str] = None
    media: Optional[list[MediaItem]] = None
    link: Optional[str] = None


class TwitterOverride(BaseModel):
    enabled: bool = True
    text: Optional[str] = None
    media: Optional[list[MediaItem]] = None
    thread: list[str] = Field(default_factory=list)


class WhatsAppOverride(BaseModel):
    enabled: bool = True
    template_name: Optional[str] = None
    template_language: str = "en"
    template_params: list[str] = Field(default_factory=list)
    recipients: list[str] = Field(default_factory=list)
    text: Optional[str] = None
    media: Optional[list[MediaItem]] = None


# ---------------------------------------------------------------------------
# Top-level content models
# ---------------------------------------------------------------------------

class DefaultContent(BaseModel):
    """Default content applied to all platforms unless overridden."""

    text: str = ""
    media: list[MediaItem] = Field(default_factory=list)


class PlatformOverrides(BaseModel):
    linkedin: Optional[LinkedInOverride] = None
    youtube: Optional[YouTubeOverride] = None
    instagram: Optional[InstagramOverride] = None
    facebook: Optional[FacebookOverride] = None
    twitter: Optional[TwitterOverride] = None
    whatsapp: Optional[WhatsAppOverride] = None


class PostFile(BaseModel):
    """Root model representing a complete content YAML/JSON file."""

    version: str = "1.0"
    defaults: DefaultContent = Field(default_factory=DefaultContent)
    platforms: PlatformOverrides = Field(default_factory=PlatformOverrides)

    def get_text(self, platform: str) -> str:
        """Return the effective text for a platform (override or default)."""
        override = getattr(self.platforms, platform, None)
        if override and hasattr(override, "text") and override.text:
            return override.text
        return self.defaults.text

    def get_media(self, platform: str) -> list[MediaItem]:
        """Return the effective media list for a platform."""
        override = getattr(self.platforms, platform, None)
        if override and hasattr(override, "media") and override.media:
            return override.media
        return self.defaults.media

    def is_platform_enabled(self, platform: str) -> bool:
        """Check if a platform is enabled in this content file."""
        override = getattr(self.platforms, platform, None)
        if override is None:
            return False
        return getattr(override, "enabled", True)

    def enabled_platforms(self) -> list[str]:
        """Return list of enabled platform names."""
        names = ["linkedin", "youtube", "instagram", "facebook", "twitter", "whatsapp"]
        return [n for n in names if self.is_platform_enabled(n)]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_content(file_path: str | Path) -> PostFile:
    """Load and parse a YAML or JSON content file into a PostFile model."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Content file not found: {path}")

    raw = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        data: dict[str, Any] = yaml.safe_load(raw) or {}
    elif path.suffix == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use .yaml, .yml, or .json")

    return PostFile.model_validate(data)


# ---------------------------------------------------------------------------
# Platform text-length limits (used by validators)
# ---------------------------------------------------------------------------

PLATFORM_TEXT_LIMITS: dict[str, int] = {
    "linkedin": 3000,
    "twitter": 280,
    "facebook": 63206,
    "instagram": 2200,
    "youtube": 5000,   # description limit
    "whatsapp": 4096,
}
