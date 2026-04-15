"""Structured logging setup for SocialPoster."""

from __future__ import annotations

import logging
import sys

from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger with Rich formatting."""
    logger = logging.getLogger("socialposter")
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


def get_logger() -> logging.Logger:
    """Return the existing socialposter logger."""
    return logging.getLogger("socialposter")
