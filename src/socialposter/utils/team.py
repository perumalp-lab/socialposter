"""Team lookup helpers."""

from __future__ import annotations

from typing import Optional


def get_current_team_id(user_id: int) -> Optional[int]:
    """Return the *team_id* for *user_id*, or ``None`` if not a member."""
    from socialposter.web.models import TeamMember

    tm = TeamMember.query.filter_by(user_id=user_id).first()
    return tm.team_id if tm else None
