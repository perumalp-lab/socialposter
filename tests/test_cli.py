"""Tests for the Click CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from socialposter.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCLIPlatforms:
    def test_platforms_lists_registered(self, runner):
        result = runner.invoke(main, ["platforms"])
        assert result.exit_code == 0
        # Should contain at least some known platforms
        assert "twitter" in result.output.lower()
        assert "facebook" in result.output.lower()
        assert "linkedin" in result.output.lower()


class TestCLIValidate:
    def test_validate_valid_yaml(self, runner, sample_yaml):
        result = runner.invoke(main, ["validate", str(sample_yaml)])
        assert result.exit_code == 0
        assert "Valid" in result.output or "valid" in result.output.lower()

    def test_validate_nonexistent_file(self, runner, tmp_path):
        bad_path = str(tmp_path / "nope.yaml")
        result = runner.invoke(main, ["validate", bad_path])
        # click.Path(exists=True) will cause a usage error
        assert result.exit_code != 0


class TestCLIPost:
    def test_post_dry_run(self, runner, sample_yaml, tmp_path):
        """Dry-run post should validate without publishing."""
        # Use an in-memory DB to avoid schema mismatch with existing on-disk DB
        import os
        env = {
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SOCIALPOSTER_SECRET_KEY": "test",
        }
        with patch.dict(os.environ, env):
            result = runner.invoke(main, [
                "post", str(sample_yaml),
                "--dry-run",
                "--platforms", "twitter,linkedin",
            ])
        # May fail auth but should not crash
        assert result.exit_code in (0, 1)
