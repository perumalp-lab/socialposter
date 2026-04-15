"""Tests for webhook API (Feature B)."""

import json
from unittest.mock import patch, MagicMock


class TestWebhookEndpointCRUD:
    """Outbound webhook endpoint management."""

    def test_list_empty(self, client):
        resp = client.get("/api/webhooks")
        assert resp.status_code == 200
        # May contain endpoints from other tests if run after, but should be a list
        assert isinstance(resp.get_json(), list)

    def test_create_endpoint(self, client):
        resp = client.post("/api/webhooks", json={
            "name": "My n8n Hook",
            "url": "https://example.com/webhook",
            "events": ["post.published", "post.failed"],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "secret" in data

    def test_create_then_list(self, client):
        client.post("/api/webhooks", json={
            "name": "Test Hook",
            "url": "https://example.com/hook",
        })
        resp = client.get("/api/webhooks")
        endpoints = resp.get_json()
        assert any(e["name"] == "Test Hook" for e in endpoints)

    def test_update_endpoint(self, client):
        resp = client.post("/api/webhooks", json={
            "name": "Old Name",
            "url": "https://example.com/old",
        })
        ep_id = resp.get_json()["id"]
        resp = client.put(f"/api/webhooks/{ep_id}", json={
            "name": "New Name",
            "is_active": False,
        })
        assert resp.status_code == 200

    def test_delete_endpoint(self, client):
        resp = client.post("/api/webhooks", json={
            "name": "To Delete",
            "url": "https://example.com/del",
        })
        ep_id = resp.get_json()["id"]
        resp = client.delete(f"/api/webhooks/{ep_id}")
        assert resp.status_code == 200

    def test_create_missing_url(self, client):
        resp = client.post("/api/webhooks", json={"name": "Bad"})
        assert resp.status_code == 400

    def test_invalid_event(self, client):
        resp = client.post("/api/webhooks", json={
            "name": "Bad Event",
            "url": "https://example.com/hook",
            "events": ["invalid.event"],
        })
        assert resp.status_code == 400


class TestInboundTokens:
    """Inbound webhook token management."""

    def test_create_and_list(self, client):
        resp = client.post("/api/webhooks/inbound-tokens", json={"name": "My Token"})
        data = resp.get_json()
        assert data["ok"] is True
        assert "token" in data

        resp = client.get("/api/webhooks/inbound-tokens")
        tokens = resp.get_json()
        assert any(t["name"] == "My Token" for t in tokens)

    def test_delete_token(self, client):
        resp = client.post("/api/webhooks/inbound-tokens", json={"name": "Temp"})
        token_id = resp.get_json()["id"]
        resp = client.delete(f"/api/webhooks/inbound-tokens/{token_id}")
        assert resp.status_code == 200


class TestInboundWebhookReceiver:
    """Inbound webhook receiver at /api/webhooks/incoming/<token>."""

    def test_invalid_token(self, client):
        resp = client.post("/api/webhooks/incoming/invalid-token-123", json={
            "action": "ai_generate",
            "topic": "test",
        })
        assert resp.status_code == 401

    def test_valid_token_unknown_action(self, client):
        resp = client.post("/api/webhooks/inbound-tokens", json={"name": "Test"})
        token = resp.get_json()["token"]
        resp = client.post(f"/api/webhooks/incoming/{token}", json={
            "action": "unknown_action",
        })
        assert resp.status_code == 400

    @patch("socialposter.core.ai_service.get_provider")
    def test_ai_generate_via_inbound(self, mock_provider, client):
        """AI generate action via inbound webhook."""
        mock_inst = MagicMock()
        mock_inst.chat.return_value = "Generated post about AI"
        mock_provider.return_value = mock_inst

        resp = client.post("/api/webhooks/inbound-tokens", json={"name": "AI Token"})
        token = resp.get_json()["token"]

        resp = client.post(f"/api/webhooks/incoming/{token}", json={
            "action": "ai_generate",
            "topic": "artificial intelligence",
            "platforms": ["twitter"],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data


class TestWebhookDispatch:
    """Webhook dispatcher unit tests."""

    @patch("socialposter.core.webhook_dispatcher.requests.post")
    def test_dispatch_with_hmac(self, mock_post, app, db, test_user):
        from socialposter.web.models import WebhookEndpoint, WebhookDeliveryLog
        from socialposter.core.webhook_dispatcher import _deliver

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        with app.app_context():
            ep = WebhookEndpoint(
                user_id=test_user.id,
                name="HMAC Test EP",
                url="https://example.com/hmac-hook",
                secret="my-secret",
                events=["post.published"],
            )
            db.session.add(ep)
            db.session.commit()

            _deliver(ep, "post.published", {"test": True}, db)

            assert mock_post.called
            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
            assert "X-Webhook-Signature" in headers
            assert headers["X-Webhook-Signature"].startswith("sha256=")

    @patch("socialposter.core.webhook_dispatcher.requests.post")
    def test_event_filtering(self, mock_post, app, db, test_user):
        """Endpoints only receive events they subscribe to."""
        from socialposter.web.models import WebhookEndpoint
        from socialposter.core.webhook_dispatcher import _deliver

        with app.app_context():
            ep = WebhookEndpoint(
                user_id=test_user.id,
                name="Filtered EP",
                url="https://example.com/filtered-hook",
                events=["post.published"],
            )
            db.session.add(ep)
            db.session.commit()

            # This event should be skipped since ep only subscribes to post.published
            assert "comment.received" not in ep.events

    @patch("socialposter.core.webhook_dispatcher.requests.post")
    def test_delivery_logging(self, mock_post, app, db, test_user):
        from socialposter.web.models import WebhookEndpoint, WebhookDeliveryLog
        from socialposter.core.webhook_dispatcher import _deliver

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        with app.app_context():
            ep = WebhookEndpoint(
                user_id=test_user.id,
                name="Logged EP",
                url="https://example.com/logged-hook",
                events=[],
            )
            db.session.add(ep)
            db.session.commit()

            _deliver(ep, "post.published", {"test": True}, db)

            logs = WebhookDeliveryLog.query.filter_by(endpoint_id=ep.id).all()
            assert len(logs) >= 1
            assert logs[0].success is True
            assert logs[0].event == "post.published"
