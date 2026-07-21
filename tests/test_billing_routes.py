"""Integration tests for billing routes — pricing, checkout, portal, webhook."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean(db):
    """Wipe billing/connection/schedule rows between tests."""
    from socialposter.web.models import (
        AppSetting, PlatformConnection, ScheduledPost, Subscription,
    )
    yield
    PlatformConnection.query.delete()
    ScheduledPost.query.delete()
    Subscription.query.delete()
    AppSetting.query.filter(AppSetting.key.like("stripe_%")).delete()
    db.session.commit()


def _set_stripe_keys():
    from socialposter.web.models import AppSetting
    AppSetting.set("stripe_secret_key", "sk_test_123")
    AppSetting.set("stripe_price_essentials_monthly", "price_ess_month_test")
    AppSetting.set("stripe_price_essentials_yearly", "price_ess_year_test")
    AppSetting.set("stripe_price_team_monthly", "price_team_month_test")
    AppSetting.set("stripe_price_team_yearly", "price_team_year_test")
    AppSetting.set("stripe_webhook_secret", "whsec_test")


# ---------------------------------------------------------------------------
# /api/billing/pricing — public, no auth
# ---------------------------------------------------------------------------

def test_public_pricing_works_without_auth(app):
    """The pricing endpoint must be reachable without a logged-in session."""
    with app.test_client() as anon:
        resp = anon.get("/api/billing/pricing")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "tiers" in body
    assert body["tiers"]["free"]["limits"]["scheduled_posts"] == 10
    assert body["tiers"]["free"]["price_monthly"] == 0
    assert body["tiers"]["essentials"]["price_yearly"] == 6000
    assert body["tiers"]["team"]["price_yearly"] == 12000


def test_public_pricing_returns_empty_prices_when_stripe_unset(app):
    with app.test_client() as anon:
        resp = anon.get("/api/billing/pricing")
    assert resp.get_json()["stripe_prices"] == {}


def test_public_pricing_includes_prices_when_stripe_configured(app):
    _set_stripe_keys()

    fake_stripe = MagicMock()

    def _fake_retrieve(price_id: str):
        prices = {
            "price_ess_month_test": SimpleNamespace(
                unit_amount=600, currency="usd", recurring=SimpleNamespace(interval="month"),
            ),
            "price_ess_year_test": SimpleNamespace(
                unit_amount=6000, currency="usd", recurring=SimpleNamespace(interval="year"),
            ),
            "price_team_month_test": SimpleNamespace(
                unit_amount=1200, currency="usd", recurring=SimpleNamespace(interval="month"),
            ),
            "price_team_year_test": SimpleNamespace(
                unit_amount=12000, currency="usd", recurring=SimpleNamespace(interval="year"),
            ),
        }
        return prices[price_id]

    fake_stripe.Price.retrieve.side_effect = _fake_retrieve
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        with app.test_client() as anon:
            resp = anon.get("/api/billing/pricing")

    body = resp.get_json()
    assert body["stripe_prices"]["essentials_month"]["amount"] == 600
    assert body["stripe_prices"]["essentials_year"]["amount"] == 6000
    assert body["stripe_prices"]["team_month"]["amount"] == 1200
    assert body["stripe_prices"]["team_year"]["amount"] == 12000


# ---------------------------------------------------------------------------
# /api/billing/plan
# ---------------------------------------------------------------------------

def test_plan_endpoint_returns_free_by_default(client):
    resp = client.get("/api/billing/plan")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["plan"] == "free"
    assert body["is_pro"] is False
    assert body["limits"]["free"]["scheduled_posts"] == 10
    assert body["limits"]["essentials"]["scheduled_posts"] == -1


def test_plan_endpoint_reflects_active_essentials_subscription(client, db, test_user):
    from socialposter.web.models import Subscription
    sub = Subscription(
        user_id=test_user.id, plan_tier="essentials", status="active",
        billing_interval="year", channels=2,
        stripe_customer_id="cus_x", stripe_subscription_id="sub_x",
    )
    db.session.add(sub)
    db.session.commit()
    body = client.get("/api/billing/plan").get_json()
    assert body["plan"] == "essentials"
    assert body["is_pro"] is True
    assert body["billing_interval"] == "year"
    assert body["channels"] == 2


# ---------------------------------------------------------------------------
# Gating: scheduled posts
# ---------------------------------------------------------------------------

def test_create_schedule_blocks_eleventh_on_free(client, db, test_user):
    """Free users can create 10 schedules; the 11th returns 402."""
    payload = {
        "name": "test",
        "platforms": ["linkedin"],
        "text": "hello",
        "interval_minutes": 60,
    }
    for i in range(10):
        resp = client.post("/api/schedules", json={**payload, "name": f"s{i}"})
        assert resp.status_code == 201

    resp = client.post("/api/schedules", json={**payload, "name": "last"})
    assert resp.status_code == 402
    body = resp.get_json()
    assert body["error"] == "plan_limit"
    assert body["kind"] == "scheduled_posts"
    assert body["limit"] == 10


def test_create_schedule_unlimited_for_essentials(client, db, test_user):
    from socialposter.web.models import Subscription
    db.session.add(Subscription(
        user_id=test_user.id, plan_tier="essentials", status="active",
    ))
    db.session.commit()

    for i in range(3):
        resp = client.post("/api/schedules", json={
            "name": f"s{i}", "platforms": ["linkedin"],
            "text": "hi", "interval_minutes": 60,
        })
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Checkout / Portal — Stripe SDK mocked
# ---------------------------------------------------------------------------

def test_checkout_returns_503_when_stripe_unconfigured(client):
    resp = client.post("/api/billing/checkout", json={
        "tier": "essentials", "interval": "month",
    })
    assert resp.status_code == 503


def test_checkout_returns_400_for_invalid_tier(client):
    _set_stripe_keys()
    resp = client.post("/api/billing/checkout", json={
        "tier": "invalid", "interval": "month",
    })
    assert resp.status_code == 400


def test_checkout_returns_400_for_invalid_interval(client):
    _set_stripe_keys()
    resp = client.post("/api/billing/checkout", json={
        "tier": "essentials", "interval": "decade",
    })
    assert resp.status_code == 400


def test_checkout_creates_session_and_customer(client, db, test_user):
    _set_stripe_keys()

    fake_stripe = MagicMock()
    fake_stripe.Customer.create.return_value = SimpleNamespace(id="cus_new_123")
    fake_stripe.checkout.Session.create.return_value = SimpleNamespace(
        url="https://checkout.stripe.com/c/pay/cs_test_123"
    )

    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post("/api/billing/checkout", json={
            "tier": "essentials", "interval": "year", "channels": 2,
        })

    assert resp.status_code == 200
    assert resp.get_json()["url"].startswith("https://checkout.stripe.com")
    fake_stripe.Customer.create.assert_called_once()

    _, kwargs = fake_stripe.checkout.Session.create.call_args
    assert kwargs["metadata"]["tier"] == "essentials"
    assert kwargs["metadata"]["interval"] == "year"
    assert kwargs["metadata"]["channels"] == "2"
    assert kwargs["line_items"][0]["quantity"] == 2

    from socialposter.web.models import Subscription
    sub = Subscription.query.filter_by(user_id=test_user.id).first()
    assert sub.stripe_customer_id == "cus_new_123"


def test_checkout_reuses_existing_customer_id(client, db, test_user):
    _set_stripe_keys()
    from socialposter.web.models import Subscription
    db.session.add(Subscription(
        user_id=test_user.id, stripe_customer_id="cus_existing", plan_tier="free",
    ))
    db.session.commit()

    fake_stripe = MagicMock()
    fake_stripe.checkout.Session.create.return_value = SimpleNamespace(url="https://x")

    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post("/api/billing/checkout", json={
            "tier": "team", "interval": "month",
        })

    assert resp.status_code == 200
    fake_stripe.Customer.create.assert_not_called()
    args, kwargs = fake_stripe.checkout.Session.create.call_args
    assert kwargs["customer"] == "cus_existing"


def test_portal_404s_when_no_customer(client):
    _set_stripe_keys()
    fake_stripe = MagicMock()
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post("/api/billing/portal")
    assert resp.status_code == 404


def test_portal_returns_session_url_when_customer_exists(client, db, test_user):
    _set_stripe_keys()
    from socialposter.web.models import Subscription
    db.session.add(Subscription(
        user_id=test_user.id, stripe_customer_id="cus_abc", plan_tier="free",
    ))
    db.session.commit()

    fake_stripe = MagicMock()
    fake_stripe.billing_portal.Session.create.return_value = SimpleNamespace(
        url="https://billing.stripe.com/session/x"
    )
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post("/api/billing/portal")

    assert resp.status_code == 200
    assert resp.get_json()["url"].startswith("https://billing.stripe.com")


# ---------------------------------------------------------------------------
# Switch interval
# ---------------------------------------------------------------------------

def test_switch_interval_404s_when_no_active_sub(client, db, test_user):
    _set_stripe_keys()
    fake_stripe = MagicMock()
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post("/api/billing/switch-interval", json={"interval": "year"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def _webhook_event(event_type: str, obj: dict) -> dict:
    return {"type": event_type, "data": {"object": obj}}


def test_webhook_rejects_invalid_signature(client):
    _set_stripe_keys()
    fake_stripe = MagicMock()
    fake_stripe.Webhook.construct_event.side_effect = Exception("bad sig")
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post(
            "/api/billing/webhook",
            data=json.dumps({"foo": "bar"}),
            headers={"Stripe-Signature": "bogus"},
            content_type="application/json",
        )
    assert resp.status_code == 400


def test_webhook_subscription_created_marks_user_paid(client, db, test_user):
    _set_stripe_keys()
    from socialposter.web.models import Subscription
    db.session.add(Subscription(
        user_id=test_user.id, stripe_customer_id="cus_abc",
    ))
    db.session.commit()

    period_end_ts = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp())
    event = _webhook_event("customer.subscription.created", {
        "id": "sub_abc",
        "customer": "cus_abc",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_end": period_end_ts,
        "items": {"data": [{
            "price": {"recurring": {"interval": "year"}},
            "quantity": 2,
        }]},
    })

    fake_stripe = MagicMock()
    fake_stripe.Webhook.construct_event.return_value = event
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post(
            "/api/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "ok"},
            content_type="application/json",
        )
    assert resp.status_code == 200

    sub = Subscription.query.filter_by(user_id=test_user.id).first()
    assert sub.plan_tier == "essentials"
    assert sub.status == "active"
    assert sub.stripe_subscription_id == "sub_abc"
    assert sub.billing_interval == "year"
    assert sub.channels == 2


def test_webhook_subscription_deleted_drops_to_free(client, db, test_user):
    _set_stripe_keys()
    from socialposter.web.models import Subscription
    db.session.add(Subscription(
        user_id=test_user.id, stripe_customer_id="cus_xyz",
        stripe_subscription_id="sub_xyz", plan_tier="essentials", status="active",
    ))
    db.session.commit()

    event = _webhook_event("customer.subscription.deleted", {
        "id": "sub_xyz",
        "customer": "cus_xyz",
        "status": "canceled",
    })
    fake_stripe = MagicMock()
    fake_stripe.Webhook.construct_event.return_value = event
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post(
            "/api/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "ok"},
            content_type="application/json",
        )
    assert resp.status_code == 200

    sub = Subscription.query.filter_by(user_id=test_user.id).first()
    assert sub.plan_tier == "free"
    assert sub.stripe_subscription_id is None


def test_webhook_ignores_unhandled_event(client):
    _set_stripe_keys()
    fake_stripe = MagicMock()
    fake_stripe.Webhook.construct_event.return_value = _webhook_event(
        "invoice.upcoming", {"id": "in_x"}
    )
    with patch("socialposter.web.billing_routes._stripe", return_value=fake_stripe):
        resp = client.post(
            "/api/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "ok"},
            content_type="application/json",
        )
    assert resp.status_code == 200
    assert resp.get_json()["ignored"] == "invoice.upcoming"
