"""Plan tiers, gate definitions, and limit enforcement.

A central place so the rest of the app doesn't sprinkle ``if user.plan == ...``
checks around. Add a new gate by extending ``LIMITS`` and calling
``enforce_plan_limit`` at the route boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

GateKind = Literal["platform_connections", "scheduled_posts", "scheduled_threads", "ideas", "api_keys", "team_members"]


@dataclass(frozen=True)
class PlanFeatureFlags:
    hashtag_manager: bool = False
    first_comment: bool = False
    advanced_analytics: bool = False
    content_approval: bool = False
    access_levels: bool = False
    notes_on_content: bool = False


@dataclass(frozen=True)
class PlanLimits:
    platform_connections: int = 3
    scheduled_posts: int = 10
    scheduled_threads: int = 1
    ideas: int = 100
    user_accounts: int = 1
    api_keys: int = 1
    features: PlanFeatureFlags = field(default_factory=PlanFeatureFlags)


TIER_META: dict[str, dict] = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "limits": PlanLimits(
            platform_connections=3,
            scheduled_posts=10,
            scheduled_threads=1,
            ideas=100,
            user_accounts=1,
            api_keys=1,
            features=PlanFeatureFlags(advanced_analytics=False),
        ),
    },
    "essentials": {
        "name": "Essentials",
        "price_monthly": 600,  # $6/mo in cents (used for yearly savings calc)
        "price_yearly": 6000,  # $60/yr — saves $12 vs $6/mo
        "limits": PlanLimits(
            platform_connections=-1,
            scheduled_posts=-1,
            scheduled_threads=-1,
            ideas=-1,
            user_accounts=1,
            api_keys=3,
            features=PlanFeatureFlags(
                hashtag_manager=True,
                first_comment=True,
                advanced_analytics=True,
            ),
        ),
    },
    "team": {
        "name": "Team",
        "price_monthly": 1200,  # $12/mo
        "price_yearly": 12000,  # $120/yr — saves $24 vs $12/mo
        "limits": PlanLimits(
            platform_connections=-1,
            scheduled_posts=-1,
            scheduled_threads=-1,
            ideas=-1,
            user_accounts=-1,
            api_keys=5,
            features=PlanFeatureFlags(
                hashtag_manager=True,
                first_comment=True,
                advanced_analytics=True,
                content_approval=True,
                access_levels=True,
                notes_on_content=True,
            ),
        ),
    },
}

LIMITS: dict[str, PlanLimits] = {
    tier: meta["limits"] for tier, meta in TIER_META.items()
}

STRIPE_PRICE_KEYS: dict[str, dict[str, str]] = {
    "essentials": {
        "month": "stripe_price_essentials_monthly",
        "year": "stripe_price_essentials_yearly",
    },
    "team": {
        "month": "stripe_price_team_monthly",
        "year": "stripe_price_team_yearly",
    },
}

PAID_TIERS = frozenset({"essentials", "team"})


class PlanLimitExceeded(Exception):
    """Raised when an action would exceed the user's plan limits."""

    def __init__(self, kind: GateKind, current: int, limit: int, plan: str):
        self.kind = kind
        self.current = current
        self.limit = limit
        self.plan = plan
        super().__init__(f"{plan} plan {kind} limit reached ({current}/{limit})")

    def to_dict(self) -> dict:
        return {
            "error": "plan_limit",
            "kind": self.kind,
            "plan": self.plan,
            "current": self.current,
            "limit": self.limit,
            "message": (
                f"Your {self.plan} plan allows up to {self.limit} "
                f"{self.kind.replace('_', ' ')}. Upgrade to increase this limit."
            ),
        }


# Facebook + Instagram + WhatsApp share one Meta OAuth flow and count as a
# single "slot" toward the platform-connection gate.
META_BUNDLE = frozenset({"facebook", "instagram", "whatsapp"})


def _connected_slots(user_id: int) -> set[str]:
    """Return the set of distinct slots a user has connected, treating the
    Meta bundle as a single slot named ``meta``.
    """
    from socialposter.web.models import PlatformConnection

    platforms = {
        row.platform for row in PlatformConnection.query.filter_by(user_id=user_id).all()
    }
    slots = platforms - META_BUNDLE
    if platforms & META_BUNDLE:
        slots.add("meta")
    return slots


def slot_for(platform: str) -> str:
    """Map a platform name to the slot it occupies under the gate."""
    return "meta" if platform in META_BUNDLE else platform


def _current_count(user_id: int, kind: GateKind) -> int:
    from socialposter.web.models import ScheduledPost

    if kind == "platform_connections":
        return len(_connected_slots(user_id))
    if kind == "scheduled_posts":
        return ScheduledPost.query.filter_by(user_id=user_id).count()
    raise ValueError(f"Unknown gate kind: {kind}")


def enforce_plan_limit(user, kind: GateKind) -> None:
    """Raise ``PlanLimitExceeded`` if creating one more ``kind`` would exceed
    the user's plan limit. No-op when within limits or on an unlimited plan.
    """
    plan_name = user.plan
    limit = getattr(LIMITS[plan_name], kind)
    if limit < 0:
        return
    current = _current_count(user.id, kind)
    if current >= limit:
        raise PlanLimitExceeded(kind=kind, current=current, limit=limit, plan=plan_name)


def tier_limits_dict(tier: str) -> dict:
    """Serialize a tier's limits into a JSON-friendly dict."""
    limits = LIMITS.get(tier)
    if not limits:
        return {}
    return {
        "platform_connections": limits.platform_connections,
        "scheduled_posts": limits.scheduled_posts,
        "scheduled_threads": limits.scheduled_threads,
        "ideas": limits.ideas,
        "user_accounts": limits.user_accounts,
        "api_keys": limits.api_keys,
        "features": {
            "hashtag_manager": limits.features.hashtag_manager,
            "first_comment": limits.features.first_comment,
            "advanced_analytics": limits.features.advanced_analytics,
            "content_approval": limits.features.content_approval,
            "access_levels": limits.features.access_levels,
            "notes_on_content": limits.features.notes_on_content,
        },
    }
