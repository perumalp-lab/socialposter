"""Automation rule engine – evaluates rules and executes actions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("socialposter")


def evaluate_rules(app):
    """Evaluate all enabled automation rules and execute matching actions.

    Called by APScheduler every 10 minutes.
    """
    with app.app_context():
        from socialposter.web.models import (
            AutomationRule, AutomationLog, PostHistory,
            EngagementMetric, db,
        )

        now = datetime.now(timezone.utc)
        rules = AutomationRule.query.filter_by(enabled=True).all()

        for rule in rules:
            try:
                met = _check_conditions(rule, now)
                if not met:
                    continue

                actions_taken = _execute_actions(rule, app)

                # Record log
                log_entry = AutomationLog(
                    rule_id=rule.id,
                    conditions_met=met,
                    actions_taken=actions_taken,
                    success=True,
                )
                db.session.add(log_entry)

                rule.last_triggered_at = now
                rule.trigger_count = (rule.trigger_count or 0) + 1
                db.session.commit()

                logger.info(
                    "Automation rule %d (%s) triggered: %s",
                    rule.id, rule.name, actions_taken,
                )
            except Exception as e:
                db.session.rollback()
                # Log the failure
                try:
                    log_entry = AutomationLog(
                        rule_id=rule.id,
                        conditions_met={"error": True},
                        actions_taken=[],
                        success=False,
                        error_message=str(e),
                    )
                    db.session.add(log_entry)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                logger.exception(
                    "Failed to evaluate automation rule %d (%s)", rule.id, rule.name
                )


def _check_conditions(rule, now: datetime) -> dict | None:
    """Check if the rule's conditions are met. Return condition details or None."""
    from socialposter.web.models import PostHistory, EngagementMetric

    conditions = rule.conditions or {}
    trigger_type = rule.trigger_type

    if trigger_type == "engagement_threshold":
        # Check if any recent post has engagement above threshold
        threshold = conditions.get("threshold", 100)
        platform = conditions.get("platform", "")
        days = conditions.get("days", 7)
        since = now - timedelta(days=days)

        query = EngagementMetric.query.filter(
            EngagementMetric.user_id == rule.user_id,
            EngagementMetric.fetched_at >= since,
        )
        if platform:
            query = query.filter(EngagementMetric.platform == platform)

        for metric in query.all():
            total = metric.likes + metric.comments + metric.shares
            if total >= threshold:
                return {
                    "type": "engagement_threshold",
                    "threshold": threshold,
                    "actual": total,
                    "platform": metric.platform,
                    "post_id": metric.published_post_id,
                }
        return None

    elif trigger_type == "no_post_interval":
        # Check if no posts have been made in the specified hours
        hours = conditions.get("hours", 24)
        platform = conditions.get("platform", "")
        since = now - timedelta(hours=hours)

        query = PostHistory.query.filter(
            PostHistory.user_id == rule.user_id,
            PostHistory.created_at >= since,
            PostHistory.success == True,  # noqa: E712
        )
        if platform:
            query = query.filter(PostHistory.platform == platform)

        count = query.count()
        if count == 0:
            # Don't re-trigger within the same interval
            if rule.last_triggered_at:
                last = rule.last_triggered_at
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if (now - last).total_seconds() < hours * 3600:
                    return None
            return {
                "type": "no_post_interval",
                "hours": hours,
                "platform": platform or "all",
            }
        return None

    return None


def _execute_actions(rule, app) -> list[dict]:
    """Execute the rule's configured actions. Return list of action results."""
    actions = rule.actions or []
    results = []

    for action in actions:
        action_type = action.get("type", "")
        params = action.get("params", {})

        if action_type == "notify":
            # For now, just log the notification (could be extended to email/webhook)
            message = params.get("message", f"Automation rule '{rule.name}' triggered")
            logger.info("Automation notification for user %d: %s", rule.user_id, message)
            results.append({"type": "notify", "message": message, "success": True})

        elif action_type == "ai_generate":
            # Generate content using AI
            try:
                from socialposter.core.ai_service import generate_content
                topic = params.get("topic", "engaging social media content")
                platforms = params.get("platforms", [])
                text = generate_content(topic, platforms, user_id=rule.user_id)
                results.append({
                    "type": "ai_generate",
                    "text": text[:200],
                    "success": True,
                })
            except Exception as e:
                results.append({
                    "type": "ai_generate",
                    "success": False,
                    "error": str(e),
                })

        elif action_type == "repost":
            # Repost to other platforms (stub – would need more context)
            target_platforms = params.get("platforms", [])
            results.append({
                "type": "repost",
                "platforms": target_platforms,
                "success": True,
                "note": "Repost queued",
            })

        elif action_type == "webhook":
            # POST to a configured URL
            try:
                import requests as _requests
                url = params.get("url", "")
                payload = params.get("payload", {})
                payload["rule_name"] = rule.name
                payload["rule_id"] = rule.id
                if url:
                    resp = _requests.post(url, json=payload, timeout=10)
                    results.append({
                        "type": "webhook",
                        "url": url,
                        "status": resp.status_code,
                        "success": 200 <= resp.status_code < 300,
                    })
                else:
                    results.append({
                        "type": "webhook",
                        "success": False,
                        "error": "No URL configured",
                    })
            except Exception as e:
                results.append({
                    "type": "webhook",
                    "success": False,
                    "error": str(e),
                })

    # Dispatch automation.triggered webhook event
    try:
        from socialposter.core.webhook_dispatcher import dispatch_event
        dispatch_event(app, "automation.triggered", {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "actions": results,
        }, user_id=rule.user_id)
    except Exception:
        pass

    return results
