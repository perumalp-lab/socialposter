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

    @property
    def plan(self) -> str:
        """Return the user's plan tier: free, essentials, or team."""
        sub = Subscription.query.filter_by(user_id=self.id).first()
        if not sub:
            return "free"
        return sub.effective_tier

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
# Subscription – per-user Stripe subscription state
# ---------------------------------------------------------------------------

# Stripe subscription statuses that grant Pro access.
PRO_STATUSES = frozenset({"active", "trialing"})

# Paid plan tiers (imported inline to avoid circular import at module level)
def _paid_tiers() -> frozenset:
    from socialposter.core.plans import PAID_TIERS
    return PAID_TIERS


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    stripe_customer_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    plan_tier = db.Column(db.String(20), nullable=False, default="free")  # free | essentials | team
    billing_interval = db.Column(db.String(10), nullable=True, default=None)  # month | year | None for free
    channels = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(40), nullable=True)  # mirrors Stripe status
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User")

    @property
    def is_pro(self) -> bool:
        return self.plan_tier in _paid_tiers() and (self.status or "") in PRO_STATUSES

    @property
    def effective_tier(self) -> str:
        if self.plan_tier in _paid_tiers() and (self.status or "") in PRO_STATUSES:
            return self.plan_tier
        return "free"


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


class UserAIKey(db.Model):
    """Per-user API key for an AI provider. Overrides workspace defaults."""
    __tablename__ = "user_ai_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # claude, openai, gemini, perplexity
    _api_key = db.Column("api_key", db.Text, nullable=False, default="")
    default_model = db.Column(db.String(100), nullable=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )

    @property
    def api_key(self) -> str:
        from socialposter.utils.crypto import decrypt_token
        return decrypt_token(self._api_key) if self._api_key else ""

    @api_key.setter
    def api_key(self, value: str) -> None:
        from socialposter.utils.crypto import encrypt_token
        self._api_key = encrypt_token(value) if value else ""


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


class Conversation(db.Model):
    """A direct-message thread between the workspace and an external participant."""

    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    platform = db.Column(db.String(50), nullable=False, index=True)
    # Stable handle for the thread on the platform, e.g. WhatsApp phone, Twitter user_id.
    platform_thread_id = db.Column(db.String(200), nullable=False)
    participant_name = db.Column(db.String(200), nullable=False, default="")
    participant_id = db.Column(db.String(200), nullable=False, default="")
    participant_avatar_url = db.Column(db.String(500), nullable=False, default="")
    last_message_text = db.Column(db.Text, nullable=False, default="")
    last_message_at = db.Column(db.DateTime, nullable=True)
    unread_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    messages = db.relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.sent_at",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "platform", "platform_thread_id", name="uq_platform_thread",
        ),
        db.Index("ix_conversation_team_last", "team_id", "last_message_at"),
    )


class Message(db.Model):
    """A single message inside a Conversation (inbound or outbound)."""

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True,
    )
    # Stable id from the platform; nullable for locally-drafted messages awaiting send.
    platform_message_id = db.Column(db.String(200), nullable=True)
    direction = db.Column(db.String(10), nullable=False)  # "in" | "out"
    sender_type = db.Column(db.String(20), nullable=False, default="customer")  # customer | user | ai
    sender_name = db.Column(db.String(200), nullable=False, default="")
    text = db.Column(db.Text, nullable=False, default="")
    sent_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    fetched_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    conversation = db.relationship("Conversation", back_populates="messages")

    __table_args__ = (
        db.UniqueConstraint(
            "conversation_id", "platform_message_id", name="uq_conversation_message",
        ),
    )


class WebhookEvent(db.Model):
    """Inbound webhook payload from a social platform."""

    __tablename__ = "webhook_events"

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False, index=True)
    event_type = db.Column(db.String(80), nullable=True, index=True)
    payload = db.Column(db.JSON, nullable=True)
    headers = db.Column(db.JSON, nullable=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    processed = db.Column(db.Boolean, nullable=False, default=False)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    processed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index("ix_webhook_platform_created", "platform", "created_at"),
    )


class ActivityLog(db.Model):
    """Audit trail of significant user actions across the workspace."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    action = db.Column(db.String(80), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.String(80), nullable=True)
    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    user = db.relationship("User")


def log_activity(
    user_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str | int] = None,
    details: Optional[dict] = None,
    *,
    autocommit: bool = True,
) -> None:
    """Persist an activity log row. Failures are swallowed — never break the
    caller's flow because of an audit-write error."""
    try:
        row = ActivityLog(
            user_id=user_id,
            action=action[:80],
            target_type=target_type[:50] if target_type else None,
            target_id=str(target_id)[:80] if target_id is not None else None,
            details=details or None,
        )
        db.session.add(row)
        if autocommit:
            db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


class Webinar(db.Model):
    __tablename__ = "webinars"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title: str = db.Column(db.String(300), nullable=False)
    description: str = db.Column(db.Text, default="")
    scheduled_at: str = db.Column(db.DateTime, nullable=True)
    duration_minutes: int = db.Column(db.Integer, default=60)
    platform_type: str = db.Column(db.String(50), default="zoom")
    meeting_url: str = db.Column(db.String(500), default="")
    registration_url: str = db.Column(db.String(500), default="")
    recording_url: str = db.Column(db.String(500), default="")
    host_name: str = db.Column(db.String(200), default="")
    target_audience: str = db.Column(db.String(200), default="")
    timezone: str = db.Column(db.String(60), default="UTC")
    tags: str = db.Column(db.JSON, default=list)
    max_attendees: int = db.Column(db.Integer, nullable=True)
    status: str = db.Column(db.String(30), default="draft")
    attendees: str = db.Column(db.JSON, default=list)
    invitations_sent_at: str = db.Column(db.DateTime, nullable=True)
    created_at: str = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: str = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailSetting(db.Model):
    __tablename__ = "email_settings"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    from_name: str = db.Column(db.String(200), default="")
    from_email: str = db.Column(db.String(200), default="")
    reply_to_email: str = db.Column(db.String(200), default="")
    smtp_host: str = db.Column(db.String(200), default="")
    smtp_port: int = db.Column(db.Integer, default=587)
    smtp_username: str = db.Column(db.String(200), default="")
    smtp_password: str = db.Column(db.String(500), default="")
    created_at: str = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: str = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


TEMPLATE_SEED = [
    ("confirmation_email_purchase", "Confirmation Email on Purchase"),
    ("reminder_email_purchase_dropoff", "Reminder Email on Purchase Drop-off"),
    ("reminder_email_failed_purchase", "Reminder Email on Failed Purchase"),
    ("reminder_email_one_day_before_expiry", "Reminder Email One Day Before Expiry"),
    ("notification_email_new_post", "Notification Email on New Post Creation"),
    ("notification_email_post_comment", "Notification Email on Post Comment"),
    ("notification_email_comment_like", "Notification Email on Comment Like"),
    ("notification_email_comment_reply", "Notification Email on Comment Reply"),
    ("notification_email_tagging_comment", "Notification Email on Tagging Someone In A Comment"),
    ("promotional_email_creation", "Promotional Email on Creation"),
    ("notification_email_single_workshop", "Notification Email on Single Workshop Creation"),
    ("notification_email_recurring_workshop", "Notification Email on Recurring Workshop Creation"),
    ("notification_email_reschedule_workshop", "Notification Email on Rescheduling a workshop"),
    ("notification_email_workshop_cancellation", "Notification Email on Workshop Cancellation"),
    ("reminder_email_24h_before_workshop", "Reminder Email 24 hours before Workshop"),
    ("reminder_email_30m_before_workshop", "Reminder Email 30 mins before Workshop"),
    ("reminder_email_15m_before_workshop", "Reminder Email 15 mins before Workshop"),
    ("post_workshop_email_15m_after", "Post Workshop Email 15 mins after Workshop"),
    ("notification_email_subscription_expired", "Notification Email after subscription expired"),
    ("notification_email_10pct_course", "Notification Email for 10% course completion"),
    ("notification_email_50pct_course", "Notification Email for 50% course completion"),
    ("notification_email_100pct_course", "Notification Email for 100% course completion"),
    ("confirmation_email_1on1_consultation", "Confirmation Email on 1-1 Consultation booking"),
    ("reminder_email_30m_before_1on1", "Reminder Email 30 mins before 1-1 Consultation"),
    ("cancellation_email_1on1_consultation", "Cancellation Email on 1-1 Consultation booking cancel"),
]


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type_key: str = db.Column(db.String(100), nullable=False)
    name: str = db.Column(db.String(300), nullable=False)
    enabled: bool = db.Column(db.Boolean, default=True)
    created_at: str = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: str = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlatformIntegration(db.Model):
    __tablename__ = "platform_integrations"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    zapier_api_key: str = db.Column(db.String(500), default="")
    pabbly_api_key: str = db.Column(db.String(500), default="")
    created_at: str = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: str = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WhatsAppMessage(db.Model):
    __tablename__ = "whatsapp_messages"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name: str = db.Column(db.String(200), nullable=False)
    template_name: str = db.Column(db.String(200), default="")
    body: str = db.Column(db.Text, default="")
    language: str = db.Column(db.String(20), default="en")
    header_type: str = db.Column(db.String(20), default="none")
    header_value: str = db.Column(db.String(500), default="")
    footer: str = db.Column(db.String(200), default="")
    created_at: str = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: str = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
