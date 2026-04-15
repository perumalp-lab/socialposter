"""Media file utilities – validation, size checks, format helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from socialposter.core.content import MediaItem, MediaType

# ---------------------------------------------------------------------------
# Per-platform constraints
# ---------------------------------------------------------------------------

# Max file sizes in bytes
MAX_IMAGE_SIZE: dict[str, int] = {
    "linkedin": 10 * 1024 * 1024,    # 10 MB
    "twitter": 5 * 1024 * 1024,      # 5 MB
    "facebook": 10 * 1024 * 1024,    # 10 MB
    "instagram": 8 * 1024 * 1024,    # 8 MB
    "whatsapp": 5 * 1024 * 1024,     # 5 MB
}

MAX_VIDEO_SIZE: dict[str, int] = {
    "linkedin": 200 * 1024 * 1024,   # 200 MB
    "twitter": 512 * 1024 * 1024,    # 512 MB
    "facebook": 1024 * 1024 * 1024,  # 1 GB
    "youtube": 128 * 1024 * 1024 * 1024,  # 128 GB
    "instagram": 100 * 1024 * 1024,  # 100 MB (Reels)
    "whatsapp": 16 * 1024 * 1024,    # 16 MB
}

ACCEPTED_IMAGE_FORMATS: dict[str, set[str]] = {
    "linkedin": {".jpg", ".jpeg", ".png", ".gif"},
    "twitter": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "facebook": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"},
    "instagram": {".jpg", ".jpeg"},  # Graph API only accepts JPEG
    "youtube": {".jpg", ".jpeg", ".png"},  # thumbnails
    "whatsapp": {".jpg", ".jpeg", ".png"},
}

ACCEPTED_VIDEO_FORMATS: dict[str, set[str]] = {
    "linkedin": {".mp4"},
    "twitter": {".mp4", ".mov"},
    "facebook": {".mp4", ".mov"},
    "youtube": {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    "instagram": {".mp4", ".mov"},
    "whatsapp": {".mp4", ".3gp"},
}


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_media(item: MediaItem, platform: str) -> list[str]:
    """Validate a media item against platform constraints. Returns error strings."""
    errors: list[str] = []
    path = Path(item.path)

    # Check file exists (skip if it's a URL)
    if not item.path.startswith("http") and not path.exists():
        errors.append(f"[{platform}] Media file not found: {item.path}")
        return errors

    # Skip further checks for URLs
    if item.path.startswith("http"):
        return errors

    suffix = path.suffix.lower()
    size = path.stat().st_size

    if item.media_type == MediaType.IMAGE:
        accepted = ACCEPTED_IMAGE_FORMATS.get(platform, set())
        if accepted and suffix not in accepted:
            errors.append(
                f"[{platform}] Image format '{suffix}' not accepted. "
                f"Use: {', '.join(sorted(accepted))}"
            )
        max_size = MAX_IMAGE_SIZE.get(platform)
        if max_size and size > max_size:
            errors.append(
                f"[{platform}] Image too large: {size / 1024 / 1024:.1f}MB "
                f"(max {max_size / 1024 / 1024:.0f}MB)"
            )

    elif item.media_type == MediaType.VIDEO:
        accepted = ACCEPTED_VIDEO_FORMATS.get(platform, set())
        if accepted and suffix not in accepted:
            errors.append(
                f"[{platform}] Video format '{suffix}' not accepted. "
                f"Use: {', '.join(sorted(accepted))}"
            )
        max_size = MAX_VIDEO_SIZE.get(platform)
        if max_size and size > max_size:
            errors.append(
                f"[{platform}] Video too large: {size / 1024 / 1024:.1f}MB "
                f"(max {max_size / 1024 / 1024:.0f}MB)"
            )

    return errors


def validate_all_media(media: list[MediaItem], platform: str) -> list[str]:
    """Validate a list of media items for a given platform."""
    errors: list[str] = []
    for item in media:
        errors.extend(validate_media(item, platform))
    return errors
