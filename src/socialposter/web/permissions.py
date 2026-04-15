"""Role-based access control decorators for team collaboration."""

from __future__ import annotations

from functools import wraps

from flask import abort, g
from flask_login import current_user

from socialposter.web.models import Team, TeamMember


def team_required(f):
    """Ensure user belongs to at least one team. Sets g.team and g.team_role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        membership = TeamMember.query.filter_by(user_id=current_user.id).first()
        if not membership:
            abort(403, description="You are not a member of any team.")
        g.team = membership.team
        g.team_role = membership.role
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Check the current user has one of the given roles in the current team.

    Must be used after @team_required so g.team_role is set.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "team_role") or g.team_role not in roles:
                abort(403, description="Insufficient permissions.")
            return f(*args, **kwargs)
        return decorated
    return decorator
