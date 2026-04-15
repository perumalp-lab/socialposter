"""SQLAlchemy models for multi-user SaaS support."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger("socialposter")

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Helper: record post history
# ---------------------------------------------------------------------------

def record_post_history(
    user_id: int,
    platform: str,
    text: str,
    success: bool,
    schedule_id: int | None = None,
    media: list | None = None,
    post_id: str | None = None,
    post_url: str | None = None,
    error_message: str | None = None,
) -> None:
    """Persist a publish event to PostHistory. Call inside an app context."""
    try:
        entry = PostHistory(
            user_id=user_id,
            schedule_id=schedule_id,
            platform=platform,
            text=text or "",
            media=media or [],
            post_id=post_id or "",
            post_url=post_url or "",
            success=success,
            error_message=error_message or "",
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to record post history")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False, default="")
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    timezone = db.Column(
        db.String(50), nullable=False, default="UTC", server_default="UTC"
    )

    connections = db.relationship(
        "PlatformConnection", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_connection(self, platform: str) -> Optional["PlatformConnection"]:
        return PlatformConnection.query.filter_by(
            user_id=self.id, platform=platform
        ).first()

    def is_connected(self, platform: str) -> bool:
        return self.get_connection(platform) is not None

    def get_team_role(self, team_id: int) -> Optional[str]:
        """Return the user's role in the given team, or None if not a member."""
        tm = TeamMember.query.filter_by(team_id=team_id, user_id=self.id).first()
        return tm.role if tm else None


class PlatformConnection(db.Model):
    __tablename__ = "platform_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    platform = db.Column(db.String(50), nullable=False, index=True)
    _access_token = db.Column("access_token", db.Text, nullable=False)
    _refresh_token = db.Column("refresh_token", db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    extra_data = db.Column(db.JSON, nullable=True)
    connected_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User", back_populates="connections")

    __table_args__ = (
        db.UniqueConstraint("user_id", "platform", name="uq_user_platform"),
    )

    # -- Encrypted token properties ------------------------------------------

    @property
    def access_token(self) -> str:
        from socialposter.utils.crypto import decrypt_token
        return decrypt_token(self._access_token) if self._access_token else ""

    @access_token.setter
    def access_token(self, value: str) -> None:
        from socialposter.utils.crypto import encrypt_token
        self._access_token = encrypt_token(value) if value else ""

    @property
    def refresh_token(self) -> Optional[str]:
        from socialposter.utils.crypto import decrypt_token
        return decrypt_token(self._refresh_token) if self._refresh_token else self._refresh_token

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]) -> None:
        from socialposter.utils.crypto import encrypt_token
        self._refresh_token = encrypt_token(value) if value else value

    @property
    def is_token_expired(self) -> bool:
        """Return True if the token has expired."""
        if self.token_expires_at is None:
            return False
        expires = self.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= datetime.now(timezone.utc)

    # -- Token refresh configuration -----------------------------------------
    # Each entry defines how to refresh tokens for a platform family.
    # Keys: setting_prefix, url, method, grant_type, default_expires,
    #       use_current_token (Meta sends the current token instead of
    #       a refresh_token), use_basic_auth, rotates_refresh.

    _REFRESH_CONFIG: dict = {
        "meta": {
            "setting_prefix": "meta",
            "url": "https://graph.facebook.com/v19.0/oauth/access_token",
            "method": "GET",
            "grant_type": "fb_exchange_token",
            "use_current_token": True,
            "default_expires": None,
            "use_basic_auth": False,
            "rotates_refresh": False,
        },
        "linkedin": {
            "setting_prefix": "linkedin",
            "url": "https://www.linkedin.com/oauth/v2/accessToken",
            "method": "POST",
            "grant_type": "refresh_token",
            "use_current_token": False,
            "default_expires": 5184000,
            "use_basic_auth": False,
            "rotates_refresh": True,
        },
        "google": {
            "setting_prefix": "google",
            "url": "https://oauth2.googleapis.com/token",
            "method": "POST",
            "grant_type": "refresh_token",
            "use_current_token": False,
            "default_expires": 3600,
            "use_basic_auth": False,
            "rotates_refresh": False,
        },
        "twitter": {
            "setting_prefix": "twitter",
            "url": "https://api.twitter.com/2/oauth2/token",
            "method": "POST",
            "grant_type": "refresh_token",
            "use_current_token": False,
            "default_expires": 7200,
            "use_basic_auth": True,
            "rotates_refresh": True,
        },
    }

    _PLATFORM_REFRESH_KEY: dict = {
        "facebook": "meta",
        "instagram": "meta",
        "whatsapp": "meta",
        "linkedin": "linkedin",
        "youtube": "google",
        "twitter": "twitter",
    }

    def ensure_fresh_token(self) -> None:
        """Check expiry and refresh the token if needed."""
        if not self.is_token_expired or not self.refresh_token:
            return
        config_key = self._PLATFORM_REFRESH_KEY.get(self.platform)
        if not config_key:
            return
        try:
            self._do_refresh(self._REFRESH_CONFIG[config_key])
            db.session.commit()
        except Exception:
            logger.warning(
                "Token refresh failed for %s (user %s)", self.platform, self.user_id
            )

    def _do_refresh(self, cfg: dict) -> None:
        """Execute a token refresh using the given configuration dict."""
        prefix = cfg["setting_prefix"]
        client_id = AppSetting.get(f"{prefix}_client_id")
        client_secret = AppSetting.get(f"{prefix}_client_secret")
        if not client_id or not client_secret:
            return

        # Build request parameters
        if cfg["use_current_token"]:
            params = {
                "grant_type": cfg["grant_type"],
                "client_id": client_id,
                "client_secret": client_secret,
                "fb_exchange_token": self.access_token,
            }
        else:
            params = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            }

        kwargs: dict = {"timeout": 15}
        if cfg["use_basic_auth"]:
            kwargs["auth"] = (client_id, client_secret)
            # When using basic auth, don't send credentials in the body
            params.pop("client_id", None)
            params.pop("client_secret", None)

        if cfg["method"] == "GET":
            resp = requests.get(cfg["url"], params=params, **kwargs)
        else:
            resp = requests.post(cfg["url"], data=params, **kwargs)

        if not resp.ok:
            return

        data = resp.json()
        self.access_token = data["access_token"]

        if cfg["rotates_refresh"] and "refresh_token" in data:
            self.refresh_token = data["refresh_token"]

        expires_in = data.get("expires_in")
        if expires_in:
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )
        elif cfg["default_expires"]:
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=cfg["default_expires"]
            )


class ScheduledPost(db.Model):
    __tablename__ = "scheduled_posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    platforms = db.Column(db.JSON, nullable=False)
    text = db.Column(db.Text, nullable=False)
    media = db.Column(db.JSON, nullable=True, default=list)
    overrides = db.Column(db.JSON, nullable=True, default=dict)
    interval_minutes = db.Column(db.Integer, nullable=False)
    next_run_at = db.Column(db.DateTime, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User")
    logs = db.relationship(
        "ScheduleLog", back_populates="schedule", cascade="all, delete-orphan"
    )


class ScheduleLog(db.Model):
    __tablename__ = "schedule_logs"

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(
        db.Integer,
        db.ForeignKey("scheduled_posts.id"),
        nullable=False,
        index=True,
    )
    executed_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    results = db.Column(db.JSON, nullable=False)

    schedule = db.relationship("ScheduledPost", back_populates="logs")


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        row = cls.query.filter_by(key=key).first()
        return row.value if row else default

    @classmethod
    def set(cls, key: str, value: str) -> None:
        row = cls.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(cls(key=key, value=value))
        db.session.commit()


# ---------------------------------------------------------------------------
# PostHistory – every publish event
# ---------------------------------------------------------------------------

class PostHistory(db.Model):
    __tablename__ = "post_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    schedule_id = db.Column(
        db.Integer, db.ForeignKey("scheduled_posts.id"), nullable=True
    )
    platform = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=False, default="")
    media = db.Column(db.JSON, nullable=True, default=list)
    post_id = db.Column(db.String(500), nullable=False, default="")
    post_url = db.Column(db.String(500), nullable=False, default="")
    success = db.Column(db.Boolean, nullable=False, default=True)
    error_message = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_post_history_user_created", "user_id", "created_at"),
        db.Index("ix_post_history_user_platform", "user_id", "platform"),
    )


# ---------------------------------------------------------------------------
# Team Collaboration
# ---------------------------------------------------------------------------

class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    members = db.relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(db.Model):
    __tablename__ = "team_members"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")  # admin, editor, viewer
    joined_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    team = db.relationship("Team", back_populates="members")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )


class DraftPost(db.Model):
    __tablename__ = "draft_posts"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False, default="Untitled Draft")
    platforms = db.Column(db.JSON, nullable=False, default=list)
    text = db.Column(db.Text, nullable=False, default="")
    media = db.Column(db.JSON, nullable=True, default=list)
    overrides = db.Column(db.JSON, nullable=True, default=dict)
    status = db.Column(
        db.String(30), nullable=False, default="draft"
    )  # draft, pending_approval, approved, rejected, published
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    review_comment = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    team = db.relationship("Team")
    author = db.relationship("User", foreign_keys=[author_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    comments = db.relationship(
        "DraftComment", back_populates="draft", cascade="all, delete-orphan",
        order_by="DraftComment.created_at",
    )


class DraftComment(db.Model):
    __tablename__ = "draft_comments"

    id = db.Column(db.Integer, primary_key=True)
    draft_id = db.Column(
        db.Integer, db.ForeignKey("draft_posts.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    draft = db.relationship("DraftPost", back_populates="comments")
    user = db.relationship("User")


# ---------------------------------------------------------------------------
# Community Management / Unified Inbox
# ---------------------------------------------------------------------------

class PublishedPost(db.Model):
    __tablename__ = "published_posts"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    platform_post_id = db.Column(db.String(500), nullable=False, default="")
    platform_post_url = db.Column(db.String(500), nullable=False, default="")
    text_preview = db.Column(db.String(300), nullable=False, default="")
    published_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_comment_fetch = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_published_post_user_platform", "user_id", "platform"),
    )


class AutomationRule(db.Model):
    __tablename__ = "automation_rules"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    trigger_type = db.Column(db.String(50), nullable=False)  # engagement_threshold, no_post_interval
    conditions = db.Column(db.JSON, nullable=False, default=dict)
    actions = db.Column(db.JSON, nullable=False, default=list)  # [{type, params}]
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    last_triggered_at = db.Column(db.DateTime, nullable=True)
    trigger_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")
    logs = db.relationship(
        "AutomationLog", back_populates="rule", cascade="all, delete-orphan"
    )


class AutomationLog(db.Model):
    __tablename__ = "automation_logs"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(
        db.Integer, db.ForeignKey("automation_rules.id"), nullable=False, index=True
    )
    triggered_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    conditions_met = db.Column(db.JSON, nullable=True)
    actions_taken = db.Column(db.JSON, nullable=True)
    success = db.Column(db.Boolean, nullable=False, default=True)
    error_message = db.Column(db.Text, nullable=False, default="")

    rule = db.relationship("AutomationRule", back_populates="logs")


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)
    media_type = db.Column(db.String(20), nullable=False, default="image")  # image, video, document
    mime_type = db.Column(db.String(100), nullable=False, default="")
    file_size = db.Column(db.Integer, nullable=False, default=0)
    tags = db.Column(db.JSON, nullable=True, default=list)
    alt_text = db.Column(db.String(500), nullable=False, default="")
    usage_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_media_user_type", "user_id", "media_type"),
    )


class UserAIConfig(db.Model):
    """Per-user AI provider API key — 'bring your own key'."""
    __tablename__ = "user_ai_configs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    provider_name = db.Column(db.String(50), nullable=False)  # claude, openai, gemini, perplexity
    _api_key = db.Column("api_key", db.Text, nullable=False, default="")
    model_id = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("user_id", "provider_name", name="uq_user_ai_provider"),
    )

    @property
    def api_key(self) -> str:
        from socialposter.utils.crypto import decrypt_token
        return decrypt_token(self._api_key) if self._api_key else ""

    @api_key.setter
    def api_key(self, value: str) -> None:
        from socialposter.utils.crypto import encrypt_token
        self._api_key = encrypt_token(value) if value else ""


class AIProviderConfig(db.Model):
    __tablename__ = "ai_provider_configs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # claude, openai, gemini, perplexity
    display_name = db.Column(db.String(100), nullable=False)
    _api_key = db.Column("api_key", db.Text, nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    models = db.relationship(
        "AIModelConfig", back_populates="provider", cascade="all, delete-orphan"
    )

    @property
    def api_key(self) -> str:
        from socialposter.utils.crypto import decrypt_token
        return decrypt_token(self._api_key) if self._api_key else ""

    @api_key.setter
    def api_key(self, value: str) -> None:
        from socialposter.utils.crypto import encrypt_token
        self._api_key = encrypt_token(value) if value else ""


class AIModelConfig(db.Model):
    __tablename__ = "ai_model_configs"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(
        db.Integer, db.ForeignKey("ai_provider_configs.id"), nullable=False
    )
    model_id = db.Column(db.String(100), nullable=False)  # e.g. "claude-sonnet-4-5-20250929"
    display_name = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    cost_tier = db.Column(db.String(20), nullable=False, default="standard")  # low, standard, premium
    max_tokens = db.Column(db.Integer, nullable=False, default=1024)

    provider = db.relationship("AIProviderConfig", back_populates="models")

    __table_args__ = (
        db.UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
    )


class EngagementMetric(db.Model):
    __tablename__ = "engagement_metrics"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_history_id = db.Column(
        db.Integer, db.ForeignKey("post_history.id"), nullable=True
    )
    published_post_id = db.Column(
        db.Integer, db.ForeignKey("published_posts.id"), nullable=True
    )
    platform = db.Column(db.String(50), nullable=False)
    likes = db.Column(db.Integer, nullable=False, default=0)
    comments = db.Column(db.Integer, nullable=False, default=0)
    shares = db.Column(db.Integer, nullable=False, default=0)
    views = db.Column(db.Integer, nullable=False, default=0)
    clicks = db.Column(db.Integer, nullable=False, default=0)
    engagement_rate = db.Column(db.Float, nullable=False, default=0.0)
    fetched_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_engagement_user_platform", "user_id", "platform"),
        db.Index("ix_engagement_user_fetched", "user_id", "fetched_at"),
    )


class InboxComment(db.Model):
    __tablename__ = "inbox_comments"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    platform = db.Column(db.String(50), nullable=False)
    platform_comment_id = db.Column(db.String(500), nullable=False)
    platform_post_id = db.Column(db.String(500), nullable=False, default="")
    platform_post_url = db.Column(db.String(500), nullable=False, default="")
    author_name = db.Column(db.String(200), nullable=False, default="")
    author_profile_url = db.Column(db.String(500), nullable=False, default="")
    author_avatar_url = db.Column(db.String(500), nullable=False, default="")
    text = db.Column(db.Text, nullable=False, default="")
    parent_comment_id = db.Column(db.String(500), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    fetched_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    posted_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("platform", "platform_comment_id", name="uq_platform_comment"),
        db.Index("ix_inbox_comment_team_read", "team_id", "is_read"),
    )


# ---------------------------------------------------------------------------
# Webhook Integration
# ---------------------------------------------------------------------------

class WebhookEndpoint(db.Model):
    """Outbound webhook subscription — delivers events via HTTP POST."""
    __tablename__ = "webhook_endpoints"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(2000), nullable=False)
    secret = db.Column(db.String(128), nullable=False, default="")
    events = db.Column(db.JSON, nullable=False, default=list)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")
    logs = db.relationship(
        "WebhookDeliveryLog", back_populates="endpoint", cascade="all, delete-orphan"
    )


class WebhookInboundToken(db.Model):
    """Inbound webhook authentication token."""
    __tablename__ = "webhook_inbound_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")


class WebhookDeliveryLog(db.Model):
    """Audit log for outbound webhook deliveries."""
    __tablename__ = "webhook_delivery_logs"

    id = db.Column(db.Integer, primary_key=True)
    endpoint_id = db.Column(
        db.Integer, db.ForeignKey("webhook_endpoints.id"), nullable=False, index=True
    )
    event = db.Column(db.String(100), nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    response_status = db.Column(db.Integer, nullable=True)
    success = db.Column(db.Boolean, nullable=False, default=False)
    error_message = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    endpoint = db.relationship("WebhookEndpoint", back_populates="logs")


# ---------------------------------------------------------------------------
# Competitor Analysis
# ---------------------------------------------------------------------------

class CompetitorAccount(db.Model):
    """A competitor account tracked by a user."""
    __tablename__ = "competitor_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    handle = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(200), nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_fetched_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")
    posts = db.relationship(
        "CompetitorPost", back_populates="competitor", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "platform", "handle", name="uq_user_competitor"),
    )


class CompetitorPost(db.Model):
    """A post fetched from a competitor account."""
    __tablename__ = "competitor_posts"

    id = db.Column(db.Integer, primary_key=True)
    competitor_id = db.Column(
        db.Integer, db.ForeignKey("competitor_accounts.id"), nullable=False, index=True
    )
    platform_post_id = db.Column(db.String(500), nullable=False)
    text = db.Column(db.Text, nullable=False, default="")
    likes = db.Column(db.Integer, nullable=False, default=0)
    comments = db.Column(db.Integer, nullable=False, default=0)
    shares = db.Column(db.Integer, nullable=False, default=0)
    views = db.Column(db.Integer, nullable=False, default=0)
    posted_at = db.Column(db.DateTime, nullable=True)
    fetched_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    competitor = db.relationship("CompetitorAccount", back_populates="posts")

    __table_args__ = (
        db.UniqueConstraint("competitor_id", "platform_post_id", name="uq_competitor_post"),
    )


class CompetitorAnalysis(db.Model):
    """AI-generated competitor analysis."""
    __tablename__ = "competitor_analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    analysis_text = db.Column(db.Text, nullable=False, default="")
    competitors = db.Column(db.JSON, nullable=False, default=list)
    period_days = db.Column(db.Integer, nullable=False, default=30)
    generated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User")
