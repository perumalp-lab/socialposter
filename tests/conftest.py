"""Shared pytest fixtures for SocialPoster tests."""

import os
import pytest
from pathlib import Path

from flask_login import login_user

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_yaml(tmp_path: Path) -> Path:
    """Create a minimal sample YAML content file for testing."""
    content = """
version: "1.0"
defaults:
  text: "Hello from SocialPoster test!"
  media: []
platforms:
  linkedin:
    enabled: true
    text: "LinkedIn test post"
  twitter:
    enabled: true
    text: "Tweet test"
  facebook:
    enabled: false
  youtube:
    enabled: false
  instagram:
    enabled: false
  whatsapp:
    enabled: false
"""
    file = tmp_path / "test_post.yaml"
    file.write_text(content)
    return file


# ---------------------------------------------------------------------------
# Web / integration fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Create a Flask app with an in-memory SQLite DB for the whole test session."""
    from socialposter.web.app import create_app
    from socialposter.web.models import db as _db

    _app = create_app(test_config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "LOGIN_DISABLED": False,
        "SECRET_KEY": "test-secret-key",
    })
    # Ensure fresh tables in the in-memory DB
    with _app.app_context():
        _db.drop_all()
        _db.create_all()
    yield _app


@pytest.fixture
def db(app):
    """Provide a clean DB session for each test."""
    from socialposter.web.models import db as _db
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()


@pytest.fixture
def test_user(db):
    """Create and return a test user."""
    from socialposter.web.models import User
    user = User(email="test@example.com", display_name="Test User", is_admin=True)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    yield user
    # Cleanup
    db.session.delete(user)
    db.session.commit()


@pytest.fixture
def client(app, test_user):
    """Provide a logged-in test client."""
    with app.test_client() as c:
        with app.test_request_context():
            login_user(test_user)
        # Use session to simulate logged-in user
        with c.session_transaction() as sess:
            sess["_user_id"] = str(test_user.id)
        yield c


def _add_connection(db, user_id, platform, token="fake-token", extra_data=None):
    """Helper to create a PlatformConnection."""
    from socialposter.web.models import PlatformConnection
    conn = PlatformConnection(
        user_id=user_id,
        platform=platform,
        access_token=token,
        extra_data=extra_data,
    )
    db.session.add(conn)
    db.session.commit()
    return conn
