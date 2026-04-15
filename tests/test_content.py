"""Tests for content parsing and validation."""

from pathlib import Path

from socialposter.core.content import load_content, PostFile, PLATFORM_TEXT_LIMITS


def test_load_yaml(sample_yaml: Path):
    """Test loading a YAML content file."""
    content = load_content(sample_yaml)
    assert isinstance(content, PostFile)
    assert content.version == "1.0"
    assert content.defaults.text == "Hello from SocialPoster test!"


def test_enabled_platforms(sample_yaml: Path):
    """Test enabled platform detection."""
    content = load_content(sample_yaml)
    enabled = content.enabled_platforms()
    assert "linkedin" in enabled
    assert "twitter" in enabled
    assert "facebook" not in enabled


def test_get_text_with_override(sample_yaml: Path):
    """Test that platform-specific text overrides the default."""
    content = load_content(sample_yaml)
    assert content.get_text("linkedin") == "LinkedIn test post"
    assert content.get_text("twitter") == "Tweet test"


def test_get_text_falls_back_to_default(sample_yaml: Path):
    """Test that missing platform text falls back to default."""
    content = load_content(sample_yaml)
    # Facebook is disabled but let's test fallback
    assert content.get_text("facebook") == "Hello from SocialPoster test!"


def test_platform_text_limits():
    """Verify text limits are defined for all platforms."""
    expected = {"linkedin", "twitter", "facebook", "instagram", "youtube", "whatsapp"}
    assert set(PLATFORM_TEXT_LIMITS.keys()) == expected


def test_load_nonexistent_file():
    """Test that loading a missing file raises FileNotFoundError."""
    import pytest
    with pytest.raises(FileNotFoundError):
        load_content("/nonexistent/file.yaml")
