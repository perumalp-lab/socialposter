"""Datetime helpers – safe formatting, user-timezone parsing, ZoneInfo lookup."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def isoformat_or(dt: datetime | None, default: str = "") -> str:
    """Return ``dt.isoformat()`` or *default* when *dt* is ``None``."""
    return dt.isoformat() if dt else default


def get_user_tz(user) -> ZoneInfo:
    """Return a ``ZoneInfo`` for *user.timezone*, falling back to UTC."""
    tz_name = getattr(user, "timezone", None) or "UTC"
    try:
        return ZoneInfo(tz_name)
    except (KeyError, Exception):
        return ZoneInfo("UTC")


def parse_user_datetime(raw_str: str, user) -> datetime:
    """Parse an ISO 8601 string and return a naive UTC datetime.

    If the parsed datetime is naive (no tzinfo) it is interpreted in the
    user's configured timezone before converting to UTC.

    Raises ``ValueError`` on invalid input.
    """
    dt = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        user_tz = get_user_tz(user)
        dt = dt.replace(tzinfo=user_tz)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
