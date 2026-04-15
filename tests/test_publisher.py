"""Tests for the publisher orchestrator (dry-run mode)."""

from pathlib import Path

from socialposter.core.publisher import publish_all


def test_dry_run_publish(sample_yaml: Path):
    """Test that dry-run validates without actually posting."""
    results = publish_all(
        content_file=str(sample_yaml),
        platforms_filter=["linkedin", "twitter"],
        dry_run=True,
        user_id=999,
    )
    # In dry-run, authentication may fail (no real credentials)
    # but the flow should complete without exceptions
    assert isinstance(results, list)


def test_publish_no_platforms(sample_yaml: Path):
    """Test publishing with no matching platforms returns empty."""
    results = publish_all(
        content_file=str(sample_yaml),
        platforms_filter=["nonexistent"],
        dry_run=True,
        user_id=999,
    )
    assert results == []
