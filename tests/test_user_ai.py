"""Tests for per-user AI key management (Feature A)."""

from unittest.mock import patch, MagicMock


class TestUserAIConfigCRUD:
    """CRUD operations on /api/user/ai/configs."""

    def test_list_empty(self, client):
        resp = client.get("/api/user/ai/configs")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_config(self, client):
        resp = client.post("/api/user/ai/configs", json={
            "provider_name": "openai",
            "api_key": "sk-test-key-123",
            "model_id": "gpt-4o",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "id" in data

    def test_create_then_list(self, client):
        client.post("/api/user/ai/configs", json={
            "provider_name": "claude",
            "api_key": "sk-ant-test",
        })
        resp = client.get("/api/user/ai/configs")
        configs = resp.get_json()
        assert any(c["provider_name"] == "claude" for c in configs)
        # API key should NOT be exposed
        for c in configs:
            assert "api_key" not in c
            assert "has_key" in c

    def test_update_existing(self, client):
        client.post("/api/user/ai/configs", json={
            "provider_name": "gemini",
            "api_key": "old-key",
        })
        resp = client.post("/api/user/ai/configs", json={
            "provider_name": "gemini",
            "api_key": "new-key",
            "model_id": "gemini-2.0-flash",
        })
        assert resp.status_code == 200

    def test_delete_config(self, client, db):
        resp = client.post("/api/user/ai/configs", json={
            "provider_name": "perplexity",
            "api_key": "pplx-key",
        })
        config_id = resp.get_json()["id"]
        resp = client.delete(f"/api/user/ai/configs/{config_id}")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/user/ai/configs/99999")
        assert resp.status_code == 404

    def test_invalid_provider_rejected(self, client):
        resp = client.post("/api/user/ai/configs", json={
            "provider_name": "invalid_provider",
            "api_key": "some-key",
        })
        assert resp.status_code == 400
        assert "Invalid provider" in resp.get_json()["error"]

    def test_missing_api_key_rejected(self, client):
        resp = client.post("/api/user/ai/configs", json={
            "provider_name": "openai",
            "api_key": "",
        })
        assert resp.status_code == 400

    def test_stored_key_accessible_via_property(self, client, db):
        """Key is stored and retrievable via the api_key property."""
        from socialposter.web.models import UserAIConfig
        client.post("/api/user/ai/configs", json={
            "provider_name": "openai",
            "api_key": "sk-secret-value",
        })
        config = UserAIConfig.query.filter_by(provider_name="openai").first()
        assert config is not None
        # Property returns the original value
        assert config.api_key == "sk-secret-value"


class TestUserAIProviderPrecedence:
    """User key takes precedence over admin key."""

    def test_user_key_used_over_admin(self, app, db, test_user):
        from socialposter.web.models import AppSetting, UserAIConfig
        from socialposter.core.ai_service import get_provider

        with app.app_context():
            # Clean up any pre-existing user AI configs
            UserAIConfig.query.filter_by(user_id=test_user.id, provider_name="openai").delete()
            db.session.commit()

            # Set up admin key
            AppSetting.set("ai_provider", "openai")
            AppSetting.set("ai_openai_api_key", "admin-key")

            # Set up user key
            uc = UserAIConfig(
                user_id=test_user.id,
                provider_name="openai",
                is_active=True,
            )
            uc.api_key = "user-key"
            db.session.add(uc)
            db.session.commit()

            provider = get_provider("openai", user_id=test_user.id)
            assert provider.api_key == "user-key"

    def test_fallback_to_admin_key(self, app, db, test_user):
        from socialposter.web.models import AppSetting, UserAIConfig
        from socialposter.core.ai_service import get_provider

        with app.app_context():
            # Clean up any pre-existing user AI configs for openai
            UserAIConfig.query.filter_by(user_id=test_user.id, provider_name="gemini").delete()
            db.session.commit()

            AppSetting.set("ai_provider", "gemini")
            AppSetting.set("ai_gemini_api_key", "admin-gemini-key")

            # No user key for gemini — should fall back to admin
            provider = get_provider("gemini", user_id=test_user.id)
            assert provider.api_key == "admin-gemini-key"
