"""Webhook receivers — capture inbound events from social platforms.

Endpoints:
  GET  /api/webhooks/<platform> — handle verification handshakes
       (Meta hub.challenge, Twitter CRC, etc.)
  POST /api/webhooks/<platform> — store payload and dispatch a per-platform
       handler. Best-effort HMAC verification when an app secret is known.

The blueprint is intentionally permissive: it stores everything it receives so
admins can debug payloads even when verification keys are misconfigured. The
`verified` flag distinguishes signed-and-validated events from raw catches.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from socialposter.web.models import AppSetting, WebhookEvent, db

log = logging.getLogger("socialposter")

webhook_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")

SUPPORTED_PLATFORMS = {
    "meta",
    "facebook",
    "instagram",
    "whatsapp",
    "linkedin",
    "twitter",
    "youtube",
}


# ── Verification helpers ──


def _meta_verify_signature(raw_body: bytes, header_value: str | None) -> bool:
    """Validate `X-Hub-Signature-256: sha256=<hmac>` against meta_client_secret."""
    if not header_value or not header_value.startswith("sha256="):
        return False
    secret = AppSetting.get("meta_client_secret")
    if not secret:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256,
    ).hexdigest()
    received = header_value.split("=", 1)[1].strip()
    return hmac.compare_digest(expected, received)


def _twitter_crc_token(crc_token: str) -> str | None:
    """Return base64-encoded HMAC-SHA256 of crc_token using the consumer secret."""
    secret = AppSetting.get("twitter_client_secret")
    if not secret:
        return None
    digest = hmac.new(
        secret.encode("utf-8"), crc_token.encode("utf-8"), hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _atom_to_dict(raw_body: bytes) -> dict | None:
    """Convert an Atom 1.0 feed (YouTube PubSubHubbub) into a JSON-friendly dict.

    Returns None if the body is not parseable XML. Strips namespace prefixes
    so handlers can address fields by simple keys (`videoId`, `channelId`, etc).
    """
    if not raw_body:
        return None
    try:
        root = ET.fromstring(raw_body)
    except ET.ParseError:
        return None

    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    def _node(elem: ET.Element) -> dict:
        out: dict = {"tag": _local(elem.tag)}
        if elem.attrib:
            out["attrib"] = {_local(k): v for k, v in elem.attrib.items()}
        text = (elem.text or "").strip()
        if text:
            out["text"] = text
        children = [_node(c) for c in elem]
        if children:
            out["children"] = children
            # Convenience: collapse single-child text fields into a flat key.
            for child in children:
                if "text" in child and "children" not in child:
                    out.setdefault(child["tag"], child["text"])
                # Promote yt:videoId-style attrs to top-level
                if child["tag"] in {"link", "author"} and child.get("attrib"):
                    href = child["attrib"].get("href")
                    if href and out.get("link") is None:
                        out["link"] = href
        return out

    return _node(root)


def _safe_headers() -> dict:
    """Snapshot a small subset of safe headers for forensics. Never store
    Authorization or cookies."""
    safe = {}
    for key in (
        "User-Agent",
        "Content-Type",
        "X-Hub-Signature",
        "X-Hub-Signature-256",
        "X-Forwarded-For",
        "X-LinkedIn-Id",
        "X-LI-Signature",
    ):
        v = request.headers.get(key)
        if v is not None:
            safe[key] = v
    return safe


# ── Handlers ──


@webhook_bp.route("/<platform>", methods=["GET"])
def webhook_verify(platform: str):
    """Handshake / verification — different platforms, different shapes."""
    if platform not in SUPPORTED_PLATFORMS:
        return jsonify({"error": f"Unsupported platform: {platform}"}), 404

    # Meta-style hub.challenge
    if request.args.get("hub.mode") == "subscribe":
        challenge = request.args.get("hub.challenge", "")
        verify_token = request.args.get("hub.verify_token", "")
        expected_token = AppSetting.get(f"webhook_verify_token_{platform}") or ""
        if expected_token and verify_token != expected_token:
            log.warning("Meta hub.verify_token mismatch for %s", platform)
            return jsonify({"error": "verify_token mismatch"}), 403
        return challenge, 200, {"Content-Type": "text/plain"}

    # Twitter Account Activity CRC
    crc_token = request.args.get("crc_token")
    if crc_token:
        response_token = _twitter_crc_token(crc_token)
        if response_token is None:
            return jsonify({"error": "twitter_client_secret not configured"}), 503
        return jsonify({"response_token": f"sha256={response_token}"})

    return jsonify({
        "ok": True,
        "platform": platform,
        "hint": (
            "POST to this URL with payloads. For Meta, append "
            "?hub.mode=subscribe&hub.challenge=...&hub.verify_token=... to "
            "verify."
        ),
    })


@webhook_bp.route("/<platform>", methods=["POST"])
def webhook_receive(platform: str):
    """Store an inbound webhook payload and dispatch to a per-platform handler."""
    if platform not in SUPPORTED_PLATFORMS:
        return jsonify({"error": f"Unsupported platform: {platform}"}), 404

    raw_body = request.get_data(cache=True)
    content_type = (request.headers.get("Content-Type") or "").lower()
    payload: dict | None = None

    # XML payloads (YouTube PubSubHubbub Atom feeds, etc.).
    is_xml = (
        "atom+xml" in content_type
        or "application/xml" in content_type
        or "text/xml" in content_type
    )
    if is_xml and raw_body:
        payload = _atom_to_dict(raw_body)

    if payload is None:
        try:
            payload = request.get_json(silent=True)
        except Exception:
            payload = None
    if payload is None and raw_body:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"_raw": raw_body[:4000].decode("utf-8", errors="replace")}

    verified = False
    if platform in {"meta", "facebook", "instagram", "whatsapp"}:
        verified = _meta_verify_signature(
            raw_body, request.headers.get("X-Hub-Signature-256"),
        )

    event_type = _detect_event_type(platform, payload or {})

    event = WebhookEvent(
        platform=platform,
        event_type=event_type,
        payload=payload,
        headers=_safe_headers(),
        verified=verified,
    )
    db.session.add(event)
    db.session.commit()

    # Best-effort dispatch — handlers should not block the response.
    try:
        _dispatch(platform, event)
        event.processed = True
        event.processed_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        log.exception("Webhook dispatch failed for %s", platform)
        event.error = str(e)[:1000]
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({"ok": True, "id": event.id, "verified": verified})


# ── Dispatch ──


def _detect_event_type(platform: str, payload: dict) -> str | None:
    """Pull a coarse event type out of the payload for filtering/searching."""
    if not isinstance(payload, dict):
        return None
    if platform in {"meta", "facebook", "instagram", "whatsapp"}:
        entries = payload.get("entry") or []
        if entries and isinstance(entries[0], dict):
            changes = entries[0].get("changes") or entries[0].get("messaging") or []
            if changes and isinstance(changes[0], dict):
                if "field" in changes[0]:
                    return f"meta.{changes[0]['field']}"
                if "value" in changes[0]:
                    return "meta.change"
        return payload.get("object")
    if platform == "linkedin":
        return payload.get("eventType") or payload.get("event")
    if platform == "twitter":
        for key in (
            "tweet_create_events",
            "favorite_events",
            "follow_events",
            "direct_message_events",
        ):
            if key in payload:
                return f"twitter.{key}"
    if platform == "youtube":
        if payload.get("tag") == "feed":
            entries = [
                c for c in (payload.get("children") or [])
                if isinstance(c, dict) and c.get("tag") == "entry"
            ]
            return f"youtube.feed.{len(entries)}_entries" if entries else "youtube.feed"
        return "youtube.feed"
    return None


def _dispatch(platform: str, event: WebhookEvent) -> None:
    """Route an event to its per-platform handler."""
    from socialposter.web.webhook_handlers import dispatch as run_handler
    summary = run_handler(platform, event.payload)
    if summary.get("stored", 0):
        log.info(
            "Webhook %s: stored %d comment(s) from event %d",
            platform, summary["stored"], event.id,
        )
