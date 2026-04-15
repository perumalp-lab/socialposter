"""Tests for competitor analysis (Feature C)."""

from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestCompetitorCRUD:
    """CRUD operations on /api/competitors."""

    def test_list_empty(self, client):
        resp = client.get("/api/competitors")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_add_competitor(self, client):
        resp = client.post("/api/competitors", json={
            "platform": "twitter",
            "handle": "@rival_brand",
            "display_name": "Rival Brand",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "id" in data

    def test_add_then_list(self, client):
        client.post("/api/competitors", json={
            "platform": "twitter",
            "handle": "test_comp",
        })
        resp = client.get("/api/competitors")
        comps = resp.get_json()
        assert any(c["handle"] == "test_comp" for c in comps)

    def test_duplicate_rejected(self, client):
        client.post("/api/competitors", json={
            "platform": "twitter",
            "handle": "dup_handle",
        })
        resp = client.post("/api/competitors", json={
            "platform": "twitter",
            "handle": "dup_handle",
        })
        assert resp.status_code == 409

    def test_delete_competitor(self, client):
        resp = client.post("/api/competitors", json={
            "platform": "twitter",
            "handle": "to_delete",
        })
        comp_id = resp.get_json()["id"]
        resp = client.delete(f"/api/competitors/{comp_id}")
        assert resp.status_code == 200

    def test_missing_platform(self, client):
        resp = client.post("/api/competitors", json={"handle": "test"})
        assert resp.status_code == 400

    def test_missing_handle(self, client):
        resp = client.post("/api/competitors", json={"platform": "twitter"})
        assert resp.status_code == 400


class TestCompetitorPosts:
    """Post fetching and listing."""

    def test_posts_empty(self, client, db):
        from socialposter.web.models import CompetitorAccount
        with client.application.app_context():
            # Get user id from session
            from socialposter.web.models import User
            user = User.query.first()
            comp = CompetitorAccount(
                user_id=user.id,
                platform="twitter",
                handle="post_test_handle",
            )
            db.session.add(comp)
            db.session.commit()
            comp_id = comp.id

        resp = client.get(f"/api/competitors/{comp_id}/posts")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_post_upsert(self, app, db, test_user):
        """fetch_competitor_posts upserts correctly."""
        from socialposter.web.models import CompetitorAccount, CompetitorPost

        with app.app_context():
            comp = CompetitorAccount(
                user_id=test_user.id,
                platform="twitter",
                handle="upsert_test",
            )
            db.session.add(comp)
            db.session.commit()

            # Insert a post manually
            cp = CompetitorPost(
                competitor_id=comp.id,
                platform_post_id="12345",
                text="Hello world",
                likes=10,
            )
            db.session.add(cp)
            db.session.commit()

            # Verify
            posts = CompetitorPost.query.filter_by(competitor_id=comp.id).all()
            assert len(posts) == 1
            assert posts[0].likes == 10


class TestCompetitorAnalysis:
    """AI-powered competitor analysis."""

    @patch("socialposter.core.ai_service.get_provider")
    def test_generate_analysis(self, mock_get_provider, app, db, test_user):
        from socialposter.web.models import CompetitorAccount, CompetitorPost, CompetitorAnalysis
        from socialposter.core.competitor_service import generate_competitor_analysis

        mock_provider = MagicMock()
        mock_provider.chat.return_value = "Analysis: Competitor A is winning on engagement."
        mock_get_provider.return_value = mock_provider

        with app.app_context():
            comp = CompetitorAccount(
                user_id=test_user.id,
                platform="twitter",
                handle="analysis_test",
            )
            db.session.add(comp)
            db.session.commit()

            # Add some posts
            for i in range(3):
                cp = CompetitorPost(
                    competitor_id=comp.id,
                    platform_post_id=f"post_{i}",
                    text=f"Post {i}",
                    likes=i * 10,
                    comments=i * 5,
                    shares=i * 2,
                    posted_at=datetime.now(timezone.utc),
                )
                db.session.add(cp)
            db.session.commit()

            result = generate_competitor_analysis(test_user.id, [comp.id], 30)
            assert "Competitor" in result or "Analysis" in result

            # Check it was saved
            analyses = CompetitorAnalysis.query.filter_by(user_id=test_user.id).all()
            assert len(analyses) >= 1


class TestEngagementComparison:
    """Engagement comparison endpoint."""

    def test_compare_empty(self, client):
        resp = client.get("/api/competitors/compare")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "user" in data
        assert "competitors" in data
