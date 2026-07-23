"""Billing blueprint – Stripe Checkout, Customer Portal, plan info, webhook.

Supports Free / Essentials / Team tiers with monthly and yearly billing
and per-channel quantity selection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from socialposter.core.plans import (
    STRIPE_PRICE_KEYS,
    TIER_META,
    tier_limits_dict,
)
from socialposter.web.models import AppSetting, Subscription, User, db
from socialposter.web.token_auth import token_or_session_required

logger = logging.getLogger("socialposter")

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")


# ---------------------------------------------------------------------------
# Stripe SDK helper
# ---------------------------------------------------------------------------

def _stripe():
    """Return the configured stripe module, or None if not set up."""
    secret = AppSetting.get("stripe_secret_key")
    if not secret:
        return None
    import stripe as stripe_sdk

    stripe_sdk.api_key = secret
    return stripe_sdk


def _frontend_origin() -> str:
    """Best-effort origin for redirect URLs back to the SPA."""
    return (
        request.headers.get("Origin")
        or request.host_url.rstrip("/")
    )


def _get_or_create_subscription(user: User) -> Subscription:
    sub = Subscription.query.filter_by(user_id=user.id).first()
    if sub is None:
        sub = Subscription(user_id=user.id, plan_tier="free", channels=1)
        db.session.add(sub)
        db.session.commit()
    return sub


def _serialize(sub: Subscription) -> dict:
    return {
        "plan": sub.effective_tier,
        "tier": sub.plan_tier,
        "is_pro": sub.is_pro,
        "billing_interval": sub.billing_interval,
        "channels": sub.channels,
        "status": sub.status,
        "current_period_end": (
            sub.current_period_end.replace(tzinfo=timezone.utc).isoformat()
            if sub.current_period_end else None
        ),
        "cancel_at_period_end": sub.cancel_at_period_end,
    }


# ---------------------------------------------------------------------------
# Public pricing — used by the logged-out marketing page
# ---------------------------------------------------------------------------

@billing_bp.route("/pricing", methods=["GET"])
def public_pricing():
    """Return all tier pricing info with features and limits.

    No authentication — this is for the public pricing page.
    """
    tiers = {}
    for tier_name, meta in TIER_META.items():
        tiers[tier_name] = {
            "name": meta["name"],
            "price_monthly": meta["price_monthly"],
            "price_yearly": meta["price_yearly"],
            "limits": tier_limits_dict(tier_name),
        }

    payload = {
        "tiers": tiers,
        "stripe_prices": _fetch_stripe_prices(),
    }
    return jsonify(payload)


def _fetch_stripe_prices() -> dict:
    """Pull amount + currency for each configured Stripe price.

    Returns a dict keyed by tier+interval, e.g.
    {"essentials_month": {...}, "essentials_year": {...}}
    """
    stripe = _stripe()
    result = {}
    for tier, intervals in STRIPE_PRICE_KEYS.items():
        for interval, setting_key in intervals.items():
            price_id = AppSetting.get(setting_key)
            if not stripe or not price_id:
                continue
            try:
                price = stripe.Price.retrieve(price_id)
                result[f"{tier}_{interval}"] = {
                    "amount": _sub_get(price, "unit_amount"),
                    "currency": _sub_get(price, "currency"),
                    "id": price_id,
                }
            except Exception:
                logger.warning("Failed to fetch Stripe price %s", price_id)
    return result


# ---------------------------------------------------------------------------
# Plan info
# ---------------------------------------------------------------------------

@billing_bp.route("/plan", methods=["GET"])
@token_or_session_required
def get_plan():
    """Return the caller's current plan + subscription state."""
    sub = _get_or_create_subscription(current_user)
    payload = _serialize(sub)
    payload["limits"] = {
        "free": tier_limits_dict("free"),
        "essentials": tier_limits_dict("essentials"),
        "team": tier_limits_dict("team"),
    }
    return jsonify(payload)


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

VALID_INTERVALS = frozenset({"month", "year"})
VALID_TIERS = frozenset({"essentials", "team"})


@billing_bp.route("/checkout", methods=["POST"])
@token_or_session_required
def create_checkout_session():
    """Create a Stripe Checkout Session and return its URL.

    JSON body:
        tier (str): "essentials" | "team"
        interval (str): "month" | "year"
        channels (int, optional): number of channels (default 1)
    """
    stripe = _stripe()
    if stripe is None:
        return jsonify({"error": "Stripe is not configured"}), 503

    data = request.get_json(force=True)
    tier = (data.get("tier") or "").strip().lower()
    interval = (data.get("interval") or "").strip().lower()
    channels = data.get("channels", 1)

    if tier not in VALID_TIERS:
        return jsonify({"error": "Invalid tier. Use 'essentials' or 'team'."}), 400
    if interval not in VALID_INTERVALS:
        return jsonify({"error": "Invalid interval. Use 'month' or 'year'."}), 400

    price_key = STRIPE_PRICE_KEYS.get(tier, {}).get(interval)
    if not price_key:
        return jsonify({"error": f"No price mapping for {tier}/{interval}"}), 500

    price_id = AppSetting.get(price_key)
    if not price_id:
        return jsonify({"error": f"Stripe price ID not configured for {tier} ({interval})"}), 503

    sub = _get_or_create_subscription(current_user)

    try:
        customer_id = sub.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.display_name or current_user.email,
                metadata={"user_id": str(current_user.id)},
            )
            customer_id = customer.id
            sub.stripe_customer_id = customer_id
            db.session.commit()

        origin = _frontend_origin()
        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": channels}],
            metadata={
                "tier": tier,
                "interval": interval,
                "channels": str(channels),
                "user_id": str(current_user.id),
            },
            success_url=f"{origin}/settings/billing?status=success",
            cancel_url=f"{origin}/settings/billing?status=cancelled",
            client_reference_id=str(current_user.id),
        )
    except Exception as exc:
        logger.exception("Stripe checkout creation failed")
        return jsonify({"error": "Stripe checkout failed", "detail": str(exc)}), 502

    return jsonify({"url": checkout_session.url})


# ---------------------------------------------------------------------------
# Switch billing interval (month ↔ year) for existing subscribers
# ---------------------------------------------------------------------------

@billing_bp.route("/switch-interval", methods=["POST"])
@token_or_session_required
def switch_billing_interval():
    """Switch an active subscription's billing interval (month ↔ year)."""
    stripe = _stripe()
    if stripe is None:
        return jsonify({"error": "Stripe is not configured"}), 503

    data = request.get_json(force=True)
    new_interval = (data.get("interval") or "").strip().lower()
    if new_interval not in VALID_INTERVALS:
        return jsonify({"error": "Invalid interval. Use 'month' or 'year'."}), 400

    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    if not sub or not sub.stripe_subscription_id or not sub.is_pro:
        return jsonify({"error": "No active paid subscription"}), 404

    current_tier = sub.plan_tier
    if current_tier not in ("essentials", "team"):
        return jsonify({"error": f"Cannot switch interval for tier '{current_tier}'"}), 400

    price_key = STRIPE_PRICE_KEYS.get(current_tier, {}).get(new_interval)
    if not price_key:
        return jsonify({"error": "Price mapping not found"}), 500

    new_price_id = AppSetting.get(price_key)
    if not new_price_id:
        return jsonify({"error": f"Stripe price not configured for {current_tier} ({new_interval})"}), 503

    try:
        subscription = stripe.Subscription.retrieve(sub.stripe_subscription_id)
        item_id = subscription["items"]["data"][0]["id"]
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            items=[{"id": item_id, "price": new_price_id}],
            proration_behavior="always_invoice",
        )
        # Forward-reference the new interval so the webhook sync matches
        sub.billing_interval = new_interval
        db.session.commit()
    except Exception as exc:
        logger.exception("Failed to switch billing interval")
        db.session.rollback()
        return jsonify({"error": "Failed to switch interval", "detail": str(exc)}), 502

    return jsonify({"ok": True, "interval": new_interval})


# ---------------------------------------------------------------------------
# Update channel count for existing subscribers
# ---------------------------------------------------------------------------

@billing_bp.route("/update-channels", methods=["POST"])
@token_or_session_required
def update_channels():
    """Update the quantity (channels) on an active subscription."""
    stripe = _stripe()
    if stripe is None:
        return jsonify({"error": "Stripe is not configured"}), 503

    data = request.get_json(force=True)
    channels = data.get("channels", 1)

    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    if not sub or not sub.stripe_subscription_id or not sub.is_pro:
        return jsonify({"error": "No active paid subscription"}), 404

    try:
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            items=[{
                "id": stripe.Subscription.retrieve(sub.stripe_subscription_id)["items"]["data"][0]["id"],
                "quantity": channels,
            }],
            proration_behavior="always_invoice",
        )
        sub.channels = channels
        db.session.commit()
    except Exception as exc:
        logger.exception("Failed to update channel count")
        db.session.rollback()
        return jsonify({"error": "Failed to update channels", "detail": str(exc)}), 502

    return jsonify({"ok": True, "channels": channels})


# ---------------------------------------------------------------------------
# Customer portal
# ---------------------------------------------------------------------------

@billing_bp.route("/portal", methods=["POST"])
@token_or_session_required
def create_portal_session():
    """Create a Stripe Customer Portal session and return its URL."""
    stripe = _stripe()
    if stripe is None:
        return jsonify({"error": "Stripe is not configured"}), 503

    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    if sub is None or not sub.stripe_customer_id:
        return jsonify({"error": "No Stripe customer for this user"}), 404

    try:
        origin = _frontend_origin()
        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{origin}/settings/billing",
        )
    except Exception as exc:
        logger.exception("Stripe portal creation failed")
        return jsonify({"error": "Stripe portal failed", "detail": str(exc)}), 502

    return jsonify({"url": session.url})


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

_HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


@billing_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Receive Stripe events and sync subscription state into the DB."""
    stripe = _stripe()
    if stripe is None:
        return jsonify({"error": "Stripe is not configured"}), 503

    secret = AppSetting.get("stripe_webhook_secret")
    if not secret:
        return jsonify({"error": "Webhook secret not configured"}), 503

    payload = request.get_data(as_text=False)
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event["type"]
    if event_type not in _HANDLED_EVENTS:
        return jsonify({"received": True, "ignored": event_type})

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(stripe, event["data"]["object"])
        elif event_type in {"customer.subscription.created",
                            "customer.subscription.updated"}:
            _apply_subscription(event["data"]["object"])
        elif event_type == "customer.subscription.deleted":
            _apply_subscription_deletion(event["data"]["object"])
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to process Stripe event %s", event_type)
        return jsonify({"error": "Event processing failed"}), 500

    return jsonify({"received": True, "type": event_type})


def _handle_checkout_completed(stripe, session_obj: dict) -> None:
    """When checkout finishes, fetch the linked subscription and apply it."""
    customer_id = session_obj.get("customer")
    sub_id = session_obj.get("subscription")
    user_ref = session_obj.get("client_reference_id")
    metadata = session_obj.get("metadata") or {}
    if not (customer_id and sub_id):
        return

    sub_row = _resolve_sub_row(customer_id=customer_id, user_ref=user_ref)
    if sub_row is None:
        logger.warning("checkout.session.completed: no Subscription row for user_ref=%s", user_ref)
        return

    sub_row.stripe_customer_id = customer_id
    # Pull tier/interval/channels from checkout metadata
    tier = metadata.get("tier", "").lower()
    if tier in ("essentials", "team"):
        sub_row.plan_tier = tier
        sub_row.channels = int(metadata.get("channels", 1))
        interval = metadata.get("interval", "month")
        sub_row.billing_interval = interval

    stripe_sub = stripe.Subscription.retrieve(sub_id)
    _apply_to_row(sub_row, stripe_sub)


def _apply_subscription(stripe_sub: dict) -> None:
    customer_id = stripe_sub.get("customer")
    sub_row = _resolve_sub_row(customer_id=customer_id)
    if sub_row is None:
        logger.warning(
            "customer.subscription event for unknown customer %s — skipping",
            customer_id,
        )
        return
    _apply_to_row(sub_row, stripe_sub)


def _apply_subscription_deletion(stripe_sub: dict) -> None:
    customer_id = stripe_sub.get("customer")
    sub_row = _resolve_sub_row(customer_id=customer_id)
    if sub_row is None:
        return
    sub_row.plan_tier = "free"
    sub_row.billing_interval = None
    sub_row.status = stripe_sub.get("status") or "canceled"
    sub_row.stripe_subscription_id = None
    sub_row.cancel_at_period_end = False
    sub_row.current_period_end = None


def _resolve_sub_row(customer_id: str | None, user_ref: str | None = None) -> Subscription | None:
    if customer_id:
        sub_row = Subscription.query.filter_by(stripe_customer_id=customer_id).first()
        if sub_row:
            return sub_row
    if user_ref:
        try:
            user_id = int(user_ref)
        except (TypeError, ValueError):
            return None
        return Subscription.query.filter_by(user_id=user_id).first()
    return None


def _apply_to_row(sub_row: Subscription, stripe_sub) -> None:
    """Copy fields from a Stripe Subscription dict-or-object into the local row."""
    sub_row.stripe_subscription_id = _sub_get(stripe_sub, "id")
    sub_row.status = _sub_get(stripe_sub, "status")
    sub_row.cancel_at_period_end = bool(_sub_get(stripe_sub, "cancel_at_period_end"))
    period_end = _sub_get(stripe_sub, "current_period_end")
    if period_end:
        sub_row.current_period_end = datetime.fromtimestamp(int(period_end), tz=timezone.utc).replace(tzinfo=None)

    # Detect tier + interval from subscription items (price metadata)
    items = _sub_get(stripe_sub, "items") or {}
    data = _sub_get(items, "data") or []
    if data:
        price = data[0].get("price", {}) if isinstance(data[0], dict) else getattr(data[0], "price", None)
        if price:
            recurring = _sub_get(price, "recurring") or {}
            interval = _sub_get(recurring, "interval")
            if interval in ("month", "year"):
                sub_row.billing_interval = interval
            quantity = int(_sub_get(data[0], "quantity") or 1)
            sub_row.channels = quantity

    status = sub_row.status or ""
    if status not in ("active", "trialing"):
        sub_row.plan_tier = "free"
        sub_row.billing_interval = None


def _sub_get(stripe_sub, key: str):
    """Stripe SDK objects support both attribute and dict access."""
    if isinstance(stripe_sub, dict):
        return stripe_sub.get(key)
    return getattr(stripe_sub, key, None)
