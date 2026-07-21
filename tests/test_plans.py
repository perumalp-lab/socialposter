"""Tests for the plans / gate helper."""

from __future__ import annotations

import pytest

from socialposter.core.plans import (
    LIMITS, PlanLimitExceeded, _connected_slots, enforce_plan_limit, slot_for,
)


def _seed_subscription(db, user_id, plan_tier, status="active"):
    from socialposter.web.models import Subscription
    sub = Subscription.query.filter_by(user_id=user_id).first()
    if sub is None:
        sub = Subscription(user_id=user_id)
        db.session.add(sub)
    sub.plan_tier = plan_tier
    sub.status = status
    db.session.commit()
    return sub


def _add_connection(db, user_id, platform, token="t"):
    from socialposter.web.models import PlatformConnection
    conn = PlatformConnection(user_id=user_id, platform=platform, access_token=token)
    db.session.add(conn)
    db.session.commit()
    return conn


@pytest.fixture(autouse=True)
def _clean_subscriptions(db):
    """Reset subscription/connection state between tests to keep counts predictable."""
    from socialposter.web.models import (
        PlatformConnection, ScheduledPost, Subscription,
    )
    yield
    PlatformConnection.query.delete()
    ScheduledPost.query.delete()
    Subscription.query.delete()
    db.session.commit()


def test_user_plan_defaults_to_free(test_user):
    assert test_user.plan == "free"


def test_user_plan_pro_when_subscription_active(db, test_user):
    _seed_subscription(db, test_user.id, "essentials", status="active")
    assert test_user.plan == "essentials"


def test_user_plan_free_when_subscription_past_due(db, test_user):
    _seed_subscription(db, test_user.id, "essentials", status="past_due")
    assert test_user.plan == "free"


def test_meta_bundle_counts_as_one_slot(db, test_user):
    _add_connection(db, test_user.id, "facebook")
    _add_connection(db, test_user.id, "instagram")
    _add_connection(db, test_user.id, "whatsapp")
    slots = _connected_slots(test_user.id)
    assert slots == {"meta"}


def test_slots_count_distinct_platforms(db, test_user):
    _add_connection(db, test_user.id, "linkedin")
    _add_connection(db, test_user.id, "twitter")
    _add_connection(db, test_user.id, "facebook")
    assert _connected_slots(test_user.id) == {"linkedin", "twitter", "meta"}


def test_slot_for_maps_meta_family():
    assert slot_for("facebook") == "meta"
    assert slot_for("instagram") == "meta"
    assert slot_for("whatsapp") == "meta"
    assert slot_for("linkedin") == "linkedin"


def test_enforce_platform_connections_free_limit(db, test_user):
    _add_connection(db, test_user.id, "linkedin")
    _add_connection(db, test_user.id, "twitter")
    _add_connection(db, test_user.id, "facebook")
    # At the free limit (3 slots — facebok is meta).
    with pytest.raises(PlanLimitExceeded) as exc:
        enforce_plan_limit(test_user, "platform_connections")
    assert exc.value.kind == "platform_connections"
    assert exc.value.current == 3
    assert exc.value.limit == 3
    assert exc.value.plan == "free"


def test_enforce_platform_connections_pro_unlimited(db, test_user):
    _seed_subscription(db, test_user.id, "essentials", status="active")
    for p in ("linkedin", "twitter", "youtube"):
        _add_connection(db, test_user.id, p)
    # No exception even at 3 connections.
    enforce_plan_limit(test_user, "platform_connections")


def test_enforce_scheduled_posts_free_limit(db, test_user):
    from datetime import datetime, timezone
    from socialposter.web.models import ScheduledPost

    for i in range(10):
        sched = ScheduledPost(
            user_id=test_user.id,
            name=f"x{i}", platforms=["linkedin"], text="t", media=[], overrides={},
            interval_minutes=60,
            next_run_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(sched)
    db.session.commit()

    with pytest.raises(PlanLimitExceeded):
        enforce_plan_limit(test_user, "scheduled_posts")


def test_plan_limit_exceeded_dict_shape():
    err = PlanLimitExceeded(kind="scheduled_posts", current=1, limit=1, plan="free")
    payload = err.to_dict()
    assert payload["error"] == "plan_limit"
    assert payload["kind"] == "scheduled_posts"
    assert payload["current"] == 1
    assert payload["limit"] == 1
    assert "Upgrade" in payload["message"]
