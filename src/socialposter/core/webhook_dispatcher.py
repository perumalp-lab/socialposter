"""Outbound webhook event dispatcher — delivers events via HTTP POST with HMAC."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger("socialposter")

# Supported event types
WEBHOOK_EVENTS = {
    "post.published",
    "post.failed",
    "comment.received",
    "engagement.threshold",
    "automation.triggered",
}


def dispatch_event(
    app,
    event: str,
    payload: dict,
    user_id: int | None = None,
) -> None:
    """Find subscribed endpoints and deliver the event.

    Runs inside an app context. Each delivery is logged to WebhookDeliveryLog.
    """
    with app.app_context():
        from socialposter.web.models import WebhookEndpoint, WebhookDeliveryLog, db

        query = WebhookEndpoint.query.filter_by(is_active=True)
        if user_id:
            query = query.filter_by(user_id=user_id)

        endpoints = query.all()

        for ep in endpoints:
            # Check if endpoint subscribes to this event
            if ep.events and event not in ep.events:
                continue

            _deliver(ep, event, payload, db)


def _deliver(endpoint, event: str, payload: dict, db) -> None:
    """POST the event to a single endpoint with HMAC signature."""
    from socialposter.web.models import WebhookDeliveryLog

    body = json.dumps({"event": event, "payload": payload}, default=str)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
    }

    # HMAC signature if secret is set
    if endpoint.secret:
        sig = hmac.new(
            endpoint.secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={sig}"

    log_entry = WebhookDeliveryLog(
        endpoint_id=endpoint.id,
        event=event,
        payload={"event": event, "payload": payload},
    )

    try:
        resp = requests.post(
            endpoint.url,
            data=body,
            headers=headers,
            timeout=10,
        )
        log_entry.response_status = resp.status_code
        log_entry.success = 200 <= resp.status_code < 300
        if not log_entry.success:
            log_entry.error_message = resp.text[:500]
    except Exception as e:
        log_entry.success = False
        log_entry.error_message = str(e)[:500]
        logger.warning("Webhook delivery failed for endpoint %d: %s", endpoint.id, e)

    try:
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
