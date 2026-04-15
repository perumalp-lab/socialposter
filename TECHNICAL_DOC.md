# SocialPoster — Technical Implementation Document

> **Version:** 0.1.0
> **Author:** Perumal Pangala
> **License:** MIT
> **Python:** >= 3.11
> **Generated:** 2026-03-19

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Database Models](#3-database-models)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [API Routes Reference](#5-api-routes-reference)
6. [Platform Plugins](#6-platform-plugins)
7. [Core Modules](#7-core-modules)
8. [Utilities](#8-utilities)
9. [Frontend](#9-frontend)
10. [Mobile (Capacitor)](#10-mobile-capacitor)
11. [Configuration & Environment](#11-configuration--environment)
12. [Testing](#12-testing)
13. [Deployment](#13-deployment)

---

## 1. Project Overview

SocialPoster is a unified social-media management application that lets users compose, schedule, and publish content to **LinkedIn, YouTube, Instagram, Facebook, X (Twitter), and WhatsApp** from a single web UI. It ships as a Flask + SQLAlchemy web app with a Click CLI, a PWA frontend, and Capacitor-based mobile shells for iOS and Android.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.x, SQLAlchemy (SQLite), Pydantic 2.x |
| Auth | Flask-Login (sessions), PyJWT (API tokens), Flask-WTF (CSRF) |
| Scheduling | APScheduler (BackgroundScheduler) |
| AI | Claude API (claude-sonnet-4-5-20250929), OpenAI API (gpt-4o) |
| Encryption | cryptography (Fernet) |
| Migrations | Flask-Migrate (Alembic) |
| Frontend | Jinja2 templates, vanilla JS, CSS (no framework) |
| Mobile | Capacitor 8.x (iOS + Android) |
| CLI | Click |
| Production WSGI | Gunicorn |

### Directory Structure

```
socialposter/
├── src/socialposter/
│   ├── __init__.py                     # version = "0.1.0"
│   ├── __main__.py
│   ├── cli.py                          # Click CLI entry point
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── content.py                  # Pydantic models, YAML/JSON loader
│   │   ├── media.py                    # Media validation constants
│   │   ├── publisher.py                # Publish orchestration
│   │   ├── ai_service.py              # AI content generation
│   │   └── scheduler.py               # APScheduler background jobs
│   │
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── registry.py                # PlatformRegistry class
│   │   ├── base.py                    # BasePlatform ABC, PostResult
│   │   ├── twitter.py
│   │   ├── linkedin.py
│   │   ├── facebook.py
│   │   ├── instagram.py
│   │   ├── youtube.py
│   │   └── whatsapp.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── crypto.py                  # Fernet token encryption
│   │   ├── logger.py                  # Rich logging
│   │   └── retry.py                   # Exponential backoff decorator
│   │
│   └── web/
│       ├── __init__.py
│       ├── app.py                     # App factory + main_bp routes
│       ├── models.py                  # SQLAlchemy models (12 tables)
│       ├── permissions.py             # team_required, role_required
│       ├── auth.py                    # Login / signup / logout
│       ├── admin.py                   # Admin settings panel
│       ├── oauth_routes.py            # OAuth connect / callback / disconnect
│       ├── token_auth.py              # JWT login / refresh
│       ├── schedule_routes.py         # Scheduled posts CRUD
│       ├── ai_routes.py               # AI generate / optimize / hashtags
│       ├── analytics_routes.py        # Post analytics & history
│       ├── calendar_routes.py         # Calendar events
│       ├── team_routes.py             # Team management
│       ├── draft_routes.py            # Draft approval workflow
│       ├── inbox_routes.py            # Community inbox
│       ├── templates/                 # 13 Jinja2 templates
│       └── static/
│           ├── css/style.css          # 1,544 lines
│           ├── js/                    # 6 JS modules (~2,042 lines)
│           ├── sw.js                  # Service Worker
│           ├── manifest.json          # PWA manifest
│           └── icons/                 # PWA icons
│
├── tests/
│   ├── conftest.py                    # Shared fixtures
│   ├── test_content.py
│   ├── test_publisher.py
│   ├── test_cli.py
│   ├── test_security.py
│   ├── test_web_fixes.py
│   └── platforms/
│       ├── test_twitter.py
│       └── test_facebook.py
│
├── ios/                               # Capacitor iOS shell
├── capacitor.config.json
├── package.json                       # Capacitor dependencies
└── pyproject.toml
```

---

## 2. Architecture

### 2.1 App Factory

The central factory function lives in `src/socialposter/web/app.py`:

```python
def create_app(test_config: dict | None = None) -> Flask:
```

**Initialization sequence:**

1. Load `.env` via `python-dotenv`
2. Create Flask instance with `template_folder` and `static_folder` pointing to `web/templates` and `web/static`
3. Set config: `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI` (SQLite), `MAX_CONTENT_LENGTH` (512 MB)
4. Apply `test_config` overrides (if provided) **before** any extension init
5. Initialize CORS (localhost origins + `capacitor://localhost`)
6. Initialize CSRF protection (`CSRFProtect`)
7. Initialize SQLAlchemy (`db.init_app`) and Flask-Migrate
8. Configure Flask-Login (`LoginManager`, `login_view="auth.login"`)
9. Register all 12 blueprints
10. Exempt API blueprints from CSRF
11. `db.create_all()` — ensure tables exist
12. Auto-migration: add `timezone` column to `users` if missing
13. Auto-migration: ensure admin users belong to a default team
14. Start background scheduler (guarded against double-start in debug reloader)

### 2.2 Blueprint Registration

| # | Blueprint | URL Prefix | CSRF | Purpose |
|---|-----------|-----------|------|---------|
| 1 | `main_bp` | `/` | Exempt | Core UI, upload, publish, profile |
| 2 | `auth_bp` | `/` | **Protected** | Login, signup, logout |
| 3 | `admin_bp` | `/admin` | **Protected** | OAuth keys, AI settings |
| 4 | `oauth_bp` | `/oauth` | **Protected** | OAuth connect/callback/disconnect |
| 5 | `schedule_bp` | `/api/schedules` | Exempt | Scheduled post CRUD + logs |
| 6 | `token_bp` | `/api/auth` | Exempt | JWT login/refresh |
| 7 | `ai_bp` | `/api/ai` | Exempt | AI generate/optimize/hashtags |
| 8 | `analytics_bp` | `/` | Exempt | Analytics summary/timeline/history |
| 9 | `calendar_bp` | `/` | Exempt | Calendar events |
| 10 | `team_bp` | `/` | Exempt | Team CRUD, invite, roles |
| 11 | `draft_bp` | `/` | Exempt | Draft approval workflow |
| 12 | `inbox_bp` | `/` | Exempt | Comment inbox + replies |

### 2.3 Plugin System

Platform plugins use a **registry + decorator** pattern:

```python
@PlatformRegistry.register
class TwitterPlatform(BasePlatform):
    ...
```

`PlatformRegistry` provides:

| Method | Description |
|--------|------------|
| `register(cls)` | Class decorator — adds plugin to `_plugins` dict keyed by `cls.name` |
| `get(name)` | Look up a registered platform by name |
| `all()` | Return all registered platform classes |
| `names()` | Return sorted list of platform names |
| `create(name)` | Instantiate and return a platform plugin by name |

### 2.4 Background Scheduler

`core/scheduler.py` uses APScheduler `BackgroundScheduler` with two recurring jobs:

| Job | Interval | Description |
|-----|----------|-------------|
| `_execute_due_posts` | Every **30 seconds** | Queries `ScheduledPost` where `enabled=True` and `next_run_at <= now(UTC)`. Publishes, logs results, advances `next_run_at`, records `PostHistory` and `PublishedPost`. |
| `_fetch_comments` | Every **5 minutes** | Iterates `PublishedPost` rows, calls `platform.fetch_comments()`, creates `InboxComment` rows for new comments, updates `last_comment_fetch`. |

Both jobs run inside a Flask app context and include graceful error handling with rollback.

---

## 3. Database Models

All models are defined in `src/socialposter/web/models.py`. The database is SQLite stored at `~/.socialposter/socialposter.db`.

### 3.1 User

**Table:** `users`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `email` | String(255) | UNIQUE, INDEXED, NOT NULL |
| `password_hash` | String(255) | NOT NULL |
| `display_name` | String(100) | DEFAULT `""` |
| `is_admin` | Boolean | DEFAULT `False`, NOT NULL |
| `created_at` | DateTime | DEFAULT `utcnow`, NOT NULL |
| `timezone` | String(50) | DEFAULT `"UTC"`, NOT NULL |

**Relationships:** `connections` → `PlatformConnection[]` (one-to-many, cascade delete-orphan)

**Methods:**
- `set_password(password)` — hash with werkzeug
- `check_password(password)` — verify hash
- `get_connection(platform)` → `Optional[PlatformConnection]`
- `is_connected(platform)` → `bool`
- `get_team_role(team_id)` → `Optional[str]`

### 3.2 PlatformConnection

**Table:** `platform_connections`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `user_id` | Integer | FK → `users.id`, INDEXED, NOT NULL |
| `platform` | String(50) | INDEXED, NOT NULL |
| `_access_token` | Text | Column name `access_token`, NOT NULL |
| `_refresh_token` | Text | Column name `refresh_token`, NULLABLE |
| `token_expires_at` | DateTime | NULLABLE |
| `extra_data` | JSON | NULLABLE |
| `connected_at` | DateTime | DEFAULT `utcnow`, NOT NULL |

**Unique constraint:** `(user_id, platform)` — `uq_user_platform`

**Encrypted properties:** `access_token` and `refresh_token` use `utils/crypto.py` getters/setters with Fernet encryption.

**Token refresh methods:**
- `ensure_fresh_token()` — checks expiry and dispatches to platform-specific refresh
- `_refresh_meta()` — Facebook/Instagram/WhatsApp long-lived token exchange
- `_refresh_linkedin()` — LinkedIn OAuth 2.0 refresh
- `_refresh_google()` — Google/YouTube OAuth 2.0 refresh
- `_refresh_twitter()` — Twitter OAuth 2.0 refresh

### 3.3 ScheduledPost

**Table:** `scheduled_posts`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `user_id` | Integer | FK → `users.id`, INDEXED, NOT NULL |
| `name` | String(200) | NOT NULL |
| `platforms` | JSON | NOT NULL (list of platform names) |
| `text` | Text | NOT NULL |
| `media` | JSON | NULLABLE, DEFAULT `[]` |
| `overrides` | JSON | NULLABLE, DEFAULT `{}` |
| `interval_minutes` | Integer | NOT NULL |
| `next_run_at` | DateTime | NOT NULL |
| `enabled` | Boolean | DEFAULT `True`, NOT NULL |
| `created_at` | DateTime | DEFAULT `utcnow`, NOT NULL |
| `updated_at` | DateTime | DEFAULT/ONUPDATE `utcnow`, NOT NULL |

**Relationships:** `logs` → `ScheduleLog[]` (one-to-many, cascade delete-orphan)

### 3.4 ScheduleLog

**Table:** `schedule_logs`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `schedule_id` | Integer | FK → `scheduled_posts.id`, INDEXED, NOT NULL |
| `executed_at` | DateTime | DEFAULT `utcnow`, NOT NULL |
| `results` | JSON | NOT NULL |

### 3.5 AppSetting

**Table:** `app_settings`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `key` | String(255) | UNIQUE, INDEXED, NOT NULL |
| `value` | Text | NOT NULL |

**Class methods:**
- `AppSetting.get(key, default="")` → `str`
- `AppSetting.set(key, value)` → `None`

### 3.6 PostHistory

**Table:** `post_history`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `user_id` | Integer | FK → `users.id`, NOT NULL |
| `schedule_id` | Integer | FK → `scheduled_posts.id`, NULLABLE |
| `platform` | String(50) | NOT NULL |
| `text` | Text | NOT NULL, DEFAULT `""` |
| `media` | JSON | NULLABLE, DEFAULT `[]` |
| `post_id` | String(500) | NOT NULL, DEFAULT `""` |
| `post_url` | String(500) | NOT NULL, DEFAULT `""` |
| `success` | Boolean | NOT NULL, DEFAULT `True` |
| `error_message` | Text | NOT NULL, DEFAULT `""` |
| `created_at` | DateTime | DEFAULT `utcnow`, NOT NULL |

**Indexes:** `(user_id, created_at)`, `(user_id, platform)`

**Helper function:**
```python
def record_post_history(user_id, platform, text, success, schedule_id=None,
                        media=None, post_id=None, post_url=None, error_message=None)
```

### 3.7 Team

**Table:** `teams`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `name` | String(200) | NOT NULL |
| `slug` | String(200) | UNIQUE, NOT NULL |
| `created_at` | DateTime | DEFAULT `utcnow`, NOT NULL |
| `created_by` | Integer | FK → `users.id`, NOT NULL |

**Relationships:** `members` → `TeamMember[]` (one-to-many, cascade delete-orphan)

### 3.8 TeamMember

**Table:** `team_members`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `team_id` | Integer | FK → `teams.id`, NOT NULL |
| `user_id` | Integer | FK → `users.id`, NOT NULL |
| `role` | String(20) | NOT NULL, DEFAULT `"viewer"` |
| `joined_at` | DateTime | DEFAULT `utcnow`, NOT NULL |

**Unique constraint:** `(team_id, user_id)` — `uq_team_user`

**Roles:** `admin`, `editor`, `viewer`

### 3.9 DraftPost

**Table:** `draft_posts`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `team_id` | Integer | FK → `teams.id`, NOT NULL |
| `author_id` | Integer | FK → `users.id`, NOT NULL |
| `name` | String(200) | NOT NULL, DEFAULT `"Untitled Draft"` |
| `platforms` | JSON | NOT NULL, DEFAULT `[]` |
| `text` | Text | NOT NULL, DEFAULT `""` |
| `media` | JSON | NULLABLE, DEFAULT `[]` |
| `overrides` | JSON | NULLABLE, DEFAULT `{}` |
| `status` | String(30) | NOT NULL, DEFAULT `"draft"` |
| `reviewed_by` | Integer | FK → `users.id`, NULLABLE |
| `review_comment` | Text | NULLABLE |
| `reviewed_at` | DateTime | NULLABLE |
| `created_at` | DateTime | DEFAULT `utcnow`, NOT NULL |
| `updated_at` | DateTime | DEFAULT/ONUPDATE `utcnow`, NOT NULL |

**Status values:** `draft` → `pending_approval` → `approved` / `rejected` → `published`

**Relationships:** `comments` → `DraftComment[]` (one-to-many, cascade delete-orphan, ordered by `created_at`)

### 3.10 DraftComment

**Table:** `draft_comments`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `draft_id` | Integer | FK → `draft_posts.id`, INDEXED, NOT NULL |
| `user_id` | Integer | FK → `users.id`, NOT NULL |
| `text` | Text | NOT NULL |
| `created_at` | DateTime | DEFAULT `utcnow`, NOT NULL |

### 3.11 PublishedPost

**Table:** `published_posts`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `team_id` | Integer | FK → `teams.id`, NULLABLE |
| `user_id` | Integer | FK → `users.id`, NOT NULL |
| `platform` | String(50) | NOT NULL |
| `platform_post_id` | String(500) | NOT NULL, DEFAULT `""` |
| `platform_post_url` | String(500) | NOT NULL, DEFAULT `""` |
| `text_preview` | String(300) | NOT NULL, DEFAULT `""` |
| `published_at` | DateTime | DEFAULT `utcnow`, NOT NULL |
| `last_comment_fetch` | DateTime | NULLABLE |

**Index:** `(user_id, platform)`

### 3.12 InboxComment

**Table:** `inbox_comments`

| Column | Type | Constraints |
|--------|------|------------|
| `id` | Integer | Primary Key |
| `team_id` | Integer | FK → `teams.id`, NULLABLE |
| `platform` | String(50) | NOT NULL |
| `platform_comment_id` | String(500) | NOT NULL |
| `platform_post_id` | String(500) | NOT NULL, DEFAULT `""` |
| `platform_post_url` | String(500) | NOT NULL, DEFAULT `""` |
| `author_name` | String(200) | NOT NULL, DEFAULT `""` |
| `author_profile_url` | String(500) | NOT NULL, DEFAULT `""` |
| `author_avatar_url` | String(500) | NOT NULL, DEFAULT `""` |
| `text` | Text | NOT NULL, DEFAULT `""` |
| `parent_comment_id` | String(500) | NULLABLE |
| `is_read` | Boolean | NOT NULL, DEFAULT `False` |
| `fetched_at` | DateTime | DEFAULT `utcnow`, NOT NULL |
| `posted_at` | DateTime | NULLABLE |

**Unique constraint:** `(platform, platform_comment_id)` — `uq_platform_comment`
**Index:** `(team_id, is_read)`

---

## 4. Authentication & Authorization

### 4.1 Session-Based Auth (Web)

Flask-Login manages browser sessions. The login manager is configured with `login_view="auth.login"`. The `@login_required` decorator protects page routes.

- **Signup:** First user is automatically promoted to admin. A default team is created and the user is added as admin.
- **Password:** Hashed with `werkzeug.security.generate_password_hash`, verified with `check_password_hash`. Minimum 8 characters.

### 4.2 JWT Bearer Tokens (API / Mobile)

The `token_bp` blueprint provides JWT-based authentication for API clients and the mobile app.

- **Algorithm:** HS256
- **Expiry:** 30 days
- **Payload:** `{sub: user_id, iat, exp}`
- **Storage:** Client stores in `localStorage['sp_auth_token']`
- **Transport:** `Authorization: Bearer <token>` header

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Authenticate with `{email, password}` → `{token, user}` |
| `/api/auth/refresh` | POST | Refresh token (Bearer header) → `{token}` |

### 4.3 Dual Auth Decorator

`@token_or_session_required` accepts either a valid Flask-Login session or a Bearer JWT. Used by API endpoints that serve both the web UI and mobile app.

### 4.4 CSRF Protection

Flask-WTF `CSRFProtect` is initialized globally. Only **form-based blueprints** are CSRF-protected:
- `auth_bp` (login, signup)
- `admin_bp` (settings)
- `oauth_bp` (connect, callback, disconnect)

All JSON API blueprints are explicitly exempted.

### 4.5 RBAC: Team Roles

**Decorators** (defined in `web/permissions.py`):

| Decorator | Effect |
|-----------|--------|
| `@team_required` | Requires team membership; sets `g.team` and `g.team_role` |
| `@role_required("admin", "editor")` | Requires one of the listed roles (must follow `@team_required`) |

**Roles:**

| Role | Permissions |
|------|------------|
| `admin` | Full access: manage team, approve/reject drafts, publish, invite members, toggle site admin |
| `editor` | Create/edit/submit/publish drafts, post content |
| `viewer` | Read-only: view drafts, inbox, analytics, calendar |

---

## 5. API Routes Reference

### 5.1 Main Blueprint (`main_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | `@login_required` | Render main composer UI |
| GET | `/connections` | `@login_required` | Platform connection status page |
| POST | `/api/connection/<platform>/config` | Token/Session | Save platform config (e.g. `page_id`, `phone_number_id`, `business_account_id`). Body: `{key: value}`. Response: `{ok, extra_data}` |
| GET | `/api/platforms` | Token/Session | List all platforms with metadata. Response: `[{name, display_name, post_types, max_text_length, connected}]` |
| POST | `/api/upload` | `@login_required` | Upload media file (multipart). Response: `{path, filename, media_type, size}`. Saves to `~/.socialposter/uploads/` |
| POST | `/api/post` | `@login_required` | Publish post. Body: `{text, platforms[], media[], overrides{}, dry_run}`. Response: `{results: [{platform, success, post_id, post_url, error}]}` |
| GET | `/api/user/profile` | Token/Session | Get current user profile. Response: `{id, email, display_name, timezone, is_admin}` |
| PUT | `/api/user/profile` | Token/Session | Update profile. Body: `{timezone?, display_name?}` |
| GET | `/offline.html` | None | PWA offline fallback page |

### 5.2 Auth Blueprint (`auth_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET, POST | `/login` | None | Login form. POST params: `email, password` |
| GET, POST | `/signup` | None | Signup form. POST params: `email, password, confirm_password, display_name, timezone`. First user auto-admin. |
| GET, POST | `/logout` | Session | Logout and redirect |

### 5.3 Admin Blueprint (`admin_bp`)

**Access:** Admin-only (enforced via `before_request` hook)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET, POST | `/admin/settings` | Admin | OAuth credentials (Meta, LinkedIn, Google, Twitter) and AI provider settings (Claude/OpenAI). GET shows masked values. POST saves non-empty fields. |

**Settings keys:** `meta_client_id`, `meta_client_secret`, `linkedin_client_id`, `linkedin_client_secret`, `google_client_id`, `google_client_secret`, `twitter_client_id`, `twitter_client_secret`, `ai_provider`, `ai_claude_api_key`, `ai_openai_api_key`

### 5.4 OAuth Blueprint (`oauth_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/oauth/<platform>/connect` | `@login_required` | Initiate OAuth flow. `?source=mobile` sets redirect flag. Supported: `meta`, `facebook`, `instagram`, `whatsapp`, `linkedin`, `youtube`, `twitter` |
| GET | `/oauth/<platform>/callback` | `@login_required` | Handle OAuth callback. Exchanges code for token, saves `PlatformConnection`. Mobile redirects to `socialposter://oauth/complete`. |
| POST | `/oauth/<platform>/disconnect` | `@login_required` | Remove connection. Meta platforms (facebook, instagram, whatsapp) disconnect together. |

**OAuth methods per platform:**

| Platform | OAuth Version | Scopes |
|----------|--------------|--------|
| Meta (FB/IG/WA) | OAuth 2.0 | `pages_show_list, pages_manage_posts, instagram_basic, instagram_content_publish, whatsapp_business_management, whatsapp_business_messaging` |
| LinkedIn | OAuth 2.0 | `openid profile w_member_social` |
| YouTube (Google) | OAuth 2.0 | `youtube.upload` (offline access) |
| Twitter/X | OAuth 2.0 + PKCE | `tweet.read tweet.write users.read offline.access` |

### 5.5 Schedule Blueprint (`schedule_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/schedules` | Token/Session | Create schedule. Body: `{name, platforms[], text, interval_minutes, media?, overrides?, start_at?}`. Validates `interval_minutes > 0`. Converts `start_at` from user timezone to UTC. Returns 201. |
| GET | `/api/schedules` | Token/Session | List all user's schedules |
| GET | `/api/schedules/<id>` | Token/Session | Get schedule + recent logs (last 10) |
| PUT | `/api/schedules/<id>` | Token/Session | Update schedule fields. Handles timezone conversion for `next_run_at`. |
| DELETE | `/api/schedules/<id>` | Token/Session | Delete schedule. Response: `{ok: true}` |
| GET | `/api/schedules/<id>/logs` | Token/Session | Paginated logs. Query: `?page=1&per_page=20` |

### 5.6 Token Auth Blueprint (`token_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | None | Authenticate. Body: `{email, password}`. Response: `{token, user: {id, email, display_name}}` |
| POST | `/api/auth/refresh` | Bearer JWT | Refresh token. Response: `{token}` |

### 5.7 AI Blueprint (`ai_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/ai/generate` | Token/Session | Generate post from topic. Body: `{topic, platforms[]}`. Response: `{text}`. Errors: 400 (no topic), 422 (validation), 502 (AI failure) |
| POST | `/api/ai/optimize` | Token/Session | Optimize text per platform. Body: `{text, platforms[]}`. Response: `{optimized: {platform: text}}` |
| POST | `/api/ai/hashtags` | Token/Session | Suggest hashtags. Body: `{text, platform, count?}` (default 5). Response: `{hashtags: [...]}` |

### 5.8 Analytics Blueprint (`analytics_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/analytics` | `@login_required` | Render analytics dashboard |
| GET | `/api/analytics/summary` | `@login_required` | Summary stats. Query: `?days=30`. Response: `{total, successes, success_rate, top_platform, platform_breakdown, days}` |
| GET | `/api/analytics/timeline` | `@login_required` | Daily post counts. Query: `?days=30`. Response: `{timeline: [{date, count}], days}` |
| GET | `/api/analytics/history` | `@login_required` | Paginated history. Query: `?page=1&per_page=20&platform=&success=`. Response: `{items[], page, per_page, total, pages}` |

### 5.9 Calendar Blueprint (`calendar_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/calendar` | `@login_required` | Render calendar page |
| GET | `/api/calendar/events` | `@login_required` | Month events. Query: `?year=YYYY&month=M`. Returns published posts and scheduled posts. All datetimes converted from UTC to user timezone. Response: `{year, month, timezone, events[]}` |

**Event types:**
- `{type: "published", date, time, platform, text, success, post_url}`
- `{type: "scheduled", date, time, platform, text, name, schedule_id}`

### 5.10 Team Blueprint (`team_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/team` | `@login_required` | Render team management page |
| POST | `/team/create` | `@login_required` | Create team (creator becomes admin). Body: `{name}`. Slugifies name. Response: `{ok, team_id, slug}` |
| POST | `/team/invite` | Team Admin | Invite user by email. Body: `{email, role}`. Response: `{ok, user_id, display_name}` |
| POST | `/team/members/<member_id>/role` | Team Admin | Change member role. Body: `{role}` (admin/editor/viewer) |
| POST | `/team/members/<user_id>/site-admin` | Team Admin + Site Admin | Toggle site admin status. Body: `{is_admin}`. Cannot change own status. |
| POST | `/team/members/<member_id>/remove` | Team Admin | Remove team member. Cannot remove self. |

### 5.11 Draft Blueprint (`draft_bp`)

**Page routes:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/drafts` | Login + Team | Drafts list page |
| GET | `/drafts/<id>` | Login + Team | Draft detail/edit page |

**API routes:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/drafts` | Admin/Editor | Create draft. Body: `{name?, platforms[], text, media[], overrides?}`. Returns 201. |
| GET | `/api/drafts` | Team Member | List team drafts. Query: `?status=`. Response: `{items: [{id, name, status, platforms, text, author, updated_at}]}` |
| GET | `/api/drafts/<id>` | Team Member | Get full draft with comments |
| PUT | `/api/drafts/<id>` | Admin/Editor | Update draft (only if `draft` or `rejected` status). Resets status to `draft`. |
| DELETE | `/api/drafts/<id>` | Admin/Editor | Delete draft |
| POST | `/api/drafts/<id>/submit` | Admin/Editor | Submit for approval → `pending_approval` |
| POST | `/api/drafts/<id>/approve` | Admin | Approve → `approved`. Body: `{comment?}` |
| POST | `/api/drafts/<id>/reject` | Admin | Reject → `rejected`. Body: `{comment?}` |
| POST | `/api/drafts/<id>/publish` | Admin/Editor | Publish approved draft to platforms → `published`. Records `PostHistory` and `PublishedPost`. |
| POST | `/api/drafts/<id>/comments` | Team Member | Add comment. Body: `{text}`. Response: `{ok, comment: {id, user, text, created_at}}` |

### 5.12 Inbox Blueprint (`inbox_bp`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/inbox` | `@login_required` | Render inbox page |
| GET | `/api/inbox/comments` | `@login_required` | List comments. Query: `?page=1&per_page=20&platform=&is_read=`. Filters by user's team. |
| POST | `/api/inbox/comments/<id>/read` | `@login_required` | Mark single comment as read |
| POST | `/api/inbox/comments/mark-read` | `@login_required` | Bulk mark read. Body: `{ids[]}`. If empty, marks all unread. |
| POST | `/api/inbox/comments/<id>/reply` | `@login_required` | Reply on platform. Body: `{text}`. Calls `platform.reply_to_comment()`. Marks as read on success. |
| GET | `/api/inbox/stats` | `@login_required` | Unread counts. Response: `{unread: {platform: count}, total_unread}` |

---

## 6. Platform Plugins

All plugins inherit from `BasePlatform` (ABC) and are registered via `@PlatformRegistry.register`.

### 6.1 Base Interface

**Abstract properties:** `name`, `display_name`, `supported_post_types`, `max_text_length`

**Abstract methods:** `authenticate(user_id) → bool`, `validate(content, user_id) → list[str]`, `publish(content, user_id) → PostResult`

**Optional methods:** `supports_comment_fetching() → bool`, `fetch_comments(user_id, post_id, since) → list[dict]`, `reply_to_comment(user_id, comment_id, post_id, text) → dict`

**Helper:** `_get_connection(user_id)` — queries `PlatformConnection` and calls `ensure_fresh_token()`

**PostResult** (dataclass):
```python
@dataclass
class PostResult:
    success: bool
    platform: str
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None
```

### 6.2 Twitter/X

| Property | Value |
|----------|-------|
| Name | `twitter` |
| Display Name | X (Twitter) |
| Post Types | TEXT, IMAGE, VIDEO, THREAD |
| Max Text | 280 |
| Auth | OAuth 2.0 Bearer Token |
| Library | `tweepy` (lazy-imported) |
| Retry | 2 attempts, 3s base delay |
| Comments | Yes (via `get_users_mentions`) |

**Key behaviors:**
- Thread support: chains tweets as replies using `in_reply_to_tweet_id`
- Authenticate via `client.get_me()`
- Reply to comment creates a reply tweet

### 6.3 LinkedIn

| Property | Value |
|----------|-------|
| Name | `linkedin` |
| Display Name | LinkedIn |
| Post Types | TEXT, IMAGE, VIDEO |
| Max Text | 3,000 |
| Auth | OAuth 2.0 Bearer Token |
| API | `https://api.linkedin.com/v2` (requests) |
| Retry | 3 attempts, 2s base delay |
| Comments | Yes (via `/socialActions/{urn}/comments`) |

**Key behaviors:**
- Gets user sub from `/userinfo`, constructs `urn:li:person:{sub}`
- Posts via `/ugcPosts` with UGC payload
- Uses URN identifiers for posts/comments

### 6.4 Facebook

| Property | Value |
|----------|-------|
| Name | `facebook` |
| Display Name | Facebook |
| Post Types | TEXT, IMAGE, VIDEO |
| Max Text | 63,206 |
| Auth | OAuth 2.0 Page Access Token |
| API | `https://graph.facebook.com/v19.0` (requests) |
| Retry | 3 attempts, 2s base delay |
| Comments | Yes (via `/{post_id}/comments`) |

**Key behaviors:**
- Requires `page_id` in `extra_data` or override
- Photo posts via `/{page_id}/photos`, text/link posts via `/{page_id}/feed`
- Supports local file uploads

### 6.5 Instagram

| Property | Value |
|----------|-------|
| Name | `instagram` |
| Display Name | Instagram |
| Post Types | IMAGE, VIDEO, CAROUSEL, REEL, STORY |
| Max Text | 2,200 |
| Auth | OAuth 2.0 (Meta Graph API) |
| API | `https://graph.facebook.com/v19.0` (requests) |
| Retry | 3 attempts, 3s base delay |
| Comments | Yes (via `/{post_id}/comments`) |

**Key behaviors:**
- **Media must be public URLs** (not local files)
- Two-step publish: create container → publish
- `business_account_id` required in `extra_data`
- Post type controlled by override (`feed` / `reel`)

### 6.6 YouTube

| Property | Value |
|----------|-------|
| Name | `youtube` |
| Display Name | YouTube |
| Post Types | VIDEO |
| Max Text | 5,000 (description) |
| Auth | OAuth 2.0 + Refresh Token |
| API | `google-api-python-client` |
| Retry | 2 attempts, 5s base delay |
| Comments | Yes (via `commentThreads().list()`) |

**Key behaviors:**
- Requires YouTube override with non-empty `title`
- Requires local video file (not HTTP URLs)
- Chunked resumable upload (10 MB chunks) via `MediaFileUpload`
- Optional thumbnail upload via `thumbnails().set()`
- Privacy: public / private / unlisted
- Default category: 28 (Science & Technology)
- Auto-refreshes Google OAuth credentials

### 6.7 WhatsApp

| Property | Value |
|----------|-------|
| Name | `whatsapp` |
| Display Name | WhatsApp |
| Post Types | TEXT, IMAGE, VIDEO |
| Max Text | 4,096 |
| Auth | OAuth 2.0 Bearer Token (Meta Cloud API) |
| API | `https://graph.facebook.com/v19.0` (requests) |
| Retry | 2 attempts, 2s base delay |
| Comments | **No** |

**Key behaviors:**
- Sends messages to individual recipients (not a traditional "post")
- Requires `phone_number_id` in `extra_data`
- Requires `recipients` list in WhatsApp override
- Two message types: **template** (with name/language/params) or **free-form text** (24h service window)
- Tracks partial success (some recipients may fail)

### Platform Comparison Summary

| Platform | Text Limit | Comment Fetch | Auth Method | Retry |
|----------|-----------|---------------|-------------|-------|
| Twitter | 280 | Yes | OAuth 2.0 | 2 × 3s |
| LinkedIn | 3,000 | Yes | OAuth 2.0 | 3 × 2s |
| Facebook | 63,206 | Yes | OAuth 2.0 (Page Token) | 3 × 2s |
| Instagram | 2,200 | Yes | OAuth 2.0 (Meta) | 3 × 3s |
| YouTube | 5,000 | Yes | OAuth 2.0 + Refresh | 2 × 5s |
| WhatsApp | 4,096 | No | OAuth 2.0 (Meta) | 2 × 2s |

---

## 7. Core Modules

### 7.1 content.py — Content Models & Loader

**Location:** `src/socialposter/core/content.py`

#### Enums

```python
class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    THUMBNAIL = "thumbnail"
    DOCUMENT = "document"

class PostType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    REEL = "reel"
    STORY = "story"
    THREAD = "thread"
```

#### Pydantic Models

| Model | Fields |
|-------|--------|
| `MediaItem` | `path: str`, `media_type: MediaType` (alias `"type"`), `alt_text: Optional[str]`, `url: Optional[str]` |
| `DefaultContent` | `text: str = ""`, `media: list[MediaItem] = []` |
| `LinkedInOverride` | `enabled`, `text`, `visibility` (`"public"`), `media` |
| `YouTubeOverride` | `enabled`, `title`, `description`, `tags: list[str]`, `category_id` (28), `privacy` (`"public"`), `media` |
| `InstagramOverride` | `enabled`, `text`, `media`, `post_type` (`"feed"`) |
| `FacebookOverride` | `enabled`, `page_id`, `text`, `media`, `link` |
| `TwitterOverride` | `enabled`, `text`, `media`, `thread: list[str]` |
| `WhatsAppOverride` | `enabled`, `template_name`, `template_language` (`"en"`), `template_params`, `recipients`, `text`, `media` |
| `PlatformOverrides` | One optional field per platform |
| `PostFile` | `version: str = "1.0"`, `defaults: DefaultContent`, `platforms: PlatformOverrides` |

#### PostFile Methods

| Method | Description |
|--------|-------------|
| `get_text(platform)` | Return override text if set, else `defaults.text` |
| `get_media(platform)` | Return override media if set, else `defaults.media` |
| `is_platform_enabled(platform)` | Check if platform override exists and `enabled=True` |
| `enabled_platforms()` | Return list of enabled platform names |

#### Loader

```python
def load_content(file_path: str | Path) -> PostFile
```
Loads `.yaml` / `.yml` / `.json` files and parses into `PostFile`. Raises `FileNotFoundError` or `ValueError`.

#### Text Limits Constant

```python
PLATFORM_TEXT_LIMITS = {
    "linkedin": 3000,
    "twitter": 280,
    "facebook": 63206,
    "instagram": 2200,
    "youtube": 5000,
    "whatsapp": 4096,
}
```

### 7.2 publisher.py — Publish Orchestration

**Location:** `src/socialposter/core/publisher.py`

| Function | Description |
|----------|-------------|
| `_resolve_platforms(content, filter_names)` | Returns list of `BasePlatform` instances. Priority: `--platforms` flag > content file enabled platforms. Warns on unknown names. |
| `_publish_one(platform, content, dry_run, user_id)` | Authenticates → validates → publishes to single platform. Returns `PostResult`. Dry run returns `post_id="DRY_RUN"`. |
| `publish_all(content_file, platforms_filter, dry_run, parallel, user_id)` | Main entry point. Loads content → resolves platforms → publishes (optionally via `ThreadPoolExecutor` for parallel execution). Prints Rich summary table. Returns `list[PostResult]`. |
| `_print_result_inline(result)` | Prints single `[OK]`/`[FAIL]` result line |
| `_print_summary(results)` | Prints Rich table with succeeded/total count |

### 7.3 scheduler.py — Background Jobs

**Location:** `src/socialposter/core/scheduler.py`

| Function | Description |
|----------|-------------|
| `_build_post_file(sched)` | Constructs `PostFile` from `ScheduledPost` DB row (reads JSON media, builds overrides) |
| `_execute_due_posts(app)` | **Runs every 30s.** Queries due posts, publishes each, writes `ScheduleLog`, updates `next_run_at`, records `PostHistory` and `PublishedPost`. Runs in app context with rollback on error. |
| `_fetch_comments(app)` | **Runs every 5min.** Fetches comments from each `PublishedPost` via platform API. Creates `InboxComment` rows for new comments. Updates `last_comment_fetch`. |
| `init_scheduler(app)` | Creates `BackgroundScheduler`, registers both jobs, starts scheduler, logs startup. |

### 7.4 media.py — Media Validation

**Location:** `src/socialposter/core/media.py`

#### Constants

**MAX_IMAGE_SIZE** (bytes):

| Platform | Limit |
|----------|-------|
| LinkedIn | 10 MB |
| Twitter | 5 MB |
| Facebook | 10 MB |
| Instagram | 8 MB |
| WhatsApp | 5 MB |

**MAX_VIDEO_SIZE** (bytes):

| Platform | Limit |
|----------|-------|
| LinkedIn | 200 MB |
| Twitter | 512 MB |
| Facebook | 1 GB |
| YouTube | 128 GB |
| Instagram | 100 MB |
| WhatsApp | 16 MB |

**ACCEPTED_IMAGE_FORMATS:**

| Platform | Formats |
|----------|---------|
| LinkedIn | .jpg, .jpeg, .png, .gif |
| Twitter | .jpg, .jpeg, .png, .gif, .webp |
| Facebook | .jpg, .jpeg, .png, .gif, .bmp, .tiff |
| Instagram | .jpg, .jpeg |
| YouTube | .jpg, .jpeg, .png (thumbnails) |
| WhatsApp | .jpg, .jpeg, .png |

**ACCEPTED_VIDEO_FORMATS:**

| Platform | Formats |
|----------|---------|
| LinkedIn | .mp4 |
| Twitter | .mp4, .mov |
| Facebook | .mp4, .mov |
| YouTube | .mp4, .mov, .avi, .mkv, .webm |
| Instagram | .mp4, .mov |
| WhatsApp | .mp4, .3gp |

#### Functions

| Function | Description |
|----------|-------------|
| `validate_media(item, platform)` | Validates single `MediaItem` against platform constraints. Checks file existence (skips HTTP URLs), format, and size. Returns list of error strings. |
| `validate_all_media(media, platform)` | Validates list of `MediaItem`. Returns combined error list. |

### 7.5 ai_service.py — AI Content Generation

**Location:** `src/socialposter/core/ai_service.py`

#### Platform Tones

Each platform has a detailed tone guideline used in AI prompts:

| Platform | Tone Summary |
|----------|-------------|
| LinkedIn | Professional and insightful (max ~3000 chars) |
| Twitter | Punchy, concise, conversational (must be under 280 chars) |
| Facebook | Friendly and engaging (up to ~63,000 chars) |
| Instagram | Visual-first storytelling (max ~2200 chars) |
| YouTube | Informative and keyword-rich (max ~5000 chars) |
| WhatsApp | Personal and direct (max ~4096 chars) |

#### AI Providers

| Provider | API URL | Model | Max Tokens |
|----------|---------|-------|-----------|
| `ClaudeProvider` | `https://api.anthropic.com/v1/messages` | claude-sonnet-4-5-20250929 | 1024 |
| `OpenAIProvider` | `https://api.openai.com/v1/chat/completions` | gpt-4o | 1024 |

`get_provider()` reads `AppSetting` for active provider and API key. Raises `ValueError` if unconfigured.

#### Functions

| Function | Description |
|----------|-------------|
| `generate_content(topic, platforms)` | Generates social post from topic using selected AI provider |
| `optimize_for_platforms(text, platforms)` | Rewrites text per platform tone/limits. Returns `dict[platform → text]`. Strips markdown fences. Falls back to original text on JSON error. |
| `suggest_hashtags(text, platform, count=5)` | Suggests relevant hashtags. Strips markdown fences. Falls back to extracting `#`-prefixed words. Returns up to `count` hashtags. |

---

## 8. Utilities

### 8.1 crypto.py — Token Encryption

**Location:** `src/socialposter/utils/crypto.py`

Uses `cryptography.fernet.Fernet` for symmetric encryption of platform tokens.

| Function | Description |
|----------|-------------|
| `_get_fernet()` | Lazily builds/caches Fernet from `SOCIALPOSTER_ENCRYPTION_KEY` env var. Returns `None` if not set or invalid. |
| `encrypt_token(plaintext)` | Encrypts token. Returns plaintext unchanged if no key configured. |
| `decrypt_token(ciphertext)` | Decrypts token. **Graceful fallback:** returns ciphertext unchanged on any error (handles plaintext tokens stored before encryption was enabled). |

### 8.2 logger.py — Rich Logging

**Location:** `src/socialposter/utils/logger.py`

| Function | Description |
|----------|-------------|
| `setup_logging(level="INFO")` | Configures `"socialposter"` logger with `RichHandler` (rich tracebacks, no path display, markup enabled). Returns logger. |
| `get_logger()` | Returns existing `"socialposter"` logger instance. |

### 8.3 retry.py — Exponential Backoff

**Location:** `src/socialposter/utils/retry.py`

```python
def retry(max_attempts=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,)):
```

Decorator for retry with exponential backoff:
- **Delay formula:** `min(base_delay * 2^(attempt-1), max_delay)`
- Re-raises original exception on final attempt
- Preserves function metadata via `functools.wraps`

---

## 9. Frontend

### 9.1 Templates (13 Jinja2 files)

All templates extend `base.html` which provides: sticky topbar, bottom mobile nav, viewport meta tags, service worker registration, and manifest link.

**Base blocks:** `{% block title %}`, `{% block body_class %}`, `{% block topbar_nav %}`, `{% block topbar_actions %}`, `{% block bottom_bar %}`, `{% block content %}`, `{% block scripts %}`

| Template | Purpose | Key Features |
|----------|---------|-------------|
| `base.html` | Master layout | Topbar, nav, bottom bar, SW registration |
| `index.html` | Main composer | 2-column (composer + preview), platform selector, text editor, media upload, AI toolbar, live preview tabs |
| `login.html` | Login form | Email/password, CSRF token, signup link |
| `signup.html` | Registration | Email, display name, password (8+ chars), timezone auto-detect (20+ IANA zones) |
| `connections.html` | Platform auth | Meta group connect, individual platform buttons, inline config inputs |
| `admin.html` | Settings panel | OAuth credentials (5 platforms), AI provider selector, masked display |
| `analytics.html` | Dashboard | Period toggle (7/30/90 days), stat cards, charts, history table |
| `calendar.html` | Content calendar | Month grid, day detail modal, event listings |
| `drafts.html` | Draft list | Status filter, new draft modal, status badges |
| `draft_detail.html` | Draft editor | Editable fields (conditionally disabled), workflow actions, comment thread |
| `inbox.html` | Comment hub | Platform/read filters, reply inline, mark read, auto-refresh |
| `team.html` | Team management | Create/invite, role selector, admin toggle, remove member |
| `offline.html` | PWA fallback | Standalone HTML, embedded CSS, reload button |

### 9.2 JavaScript Modules (6 files, ~2,042 lines)

| Module | Lines | Purpose |
|--------|-------|---------|
| `app.js` | 1,145 | Main composer: platform selection, media upload, overrides, live preview, publishing, AI features, mobile integration |
| `drafts.js` | 270 | Draft list/detail: CRUD, workflow (submit/approve/reject/publish), comments |
| `inbox.js` | 179 | Comment inbox: list, filters, mark read, reply, 60s auto-refresh stats |
| `analytics.js` | 165 | Dashboard: summary cards, timeline chart, history table with filters |
| `calendar.js` | 164 | Month view: grid rendering, day modal, event chips |
| `team.js` | 119 | Team management: create, invite, role change, admin toggle, remove |

**Shared patterns:**
- `apiFetch(path, options)` — wrapper that injects `Authorization: Bearer` from `localStorage`
- `escHtml()`, `escAttr()` — XSS prevention helpers
- `toast(message, type)` — notification system (4s auto-dismiss)
- `PLATFORM_META` — colors, letters, CSS classes per platform

**AI features in `app.js`:**
- `doAIGenerate()` — POST `/api/ai/generate` → fills textarea
- `optimizeAllPlatforms()` — POST `/api/ai/optimize` → fills override fields
- `suggestHashtags()` — POST `/api/ai/hashtags` → appends to text
- `autoFillYouTube()` — syncs description from main text

**Mobile features in `app.js`:**
- Capacitor detection: `typeof window.Capacitor !== "undefined"`
- Camera: `Capacitor.Plugins.Camera.getPhoto()` → upload
- StatusBar: `setBackgroundColor("#6366f1")`, `setStyle("LIGHT")`
- Deep links: `addListener("appUrlOpen")` for `socialposter://oauth/complete`
- Pull-to-refresh: touch swipe detect (80px threshold)

### 9.3 CSS (`style.css` — 1,544 lines)

**Design system variables:**

```css
--bg: #f8fafc;          --surface: #fff;
--border: #e2e8f0;      --text: #0f172a;
--text-secondary: #64748b;  --text-muted: #94a3b8;
--primary: #6366f1;     --primary-hover: #4f46e5;
--success: #10b981;     --warning: #f59e0b;    --danger: #ef4444;
--radius: 12px;         --radius-sm: 8px;
--shadow-sm / --shadow / --shadow-lg
--transition: 150ms ease;
Font: Inter + system fallbacks
```

**Key sections:**

| Section | Details |
|---------|---------|
| Topbar | Sticky, z-index 100, logo + nav flex |
| Buttons | Primary (indigo), outline, danger; btn-sm size; hover/active/disabled states |
| Layout | 2-column grid (1fr / 420px) → 1-column on mobile; max-width 1400px |
| Cards | White bg, border, 12px radius, shadow-sm |
| Platform Grid | Auto-fill (140px min), chips with brand colors |
| Textarea | Focus glow (primary), placeholder muted |
| Char Counter | Absolute positioned, color transitions (warn at 90%, over at limit) |
| Upload Zone | Dashed border, dragover highlight, 110px media thumbnails |
| Preview Panel | Sticky top 84px, mock social post |
| Toast | Fixed bottom-right, slide-up animation, color-coded border |
| Loading | Full-screen backdrop blur, centered spinner |
| Auth Forms | Centered max-width 420px |

**Responsive breakpoints:**
- `< 768px` — Mobile: hamburger menu, bottom navigation bar, 48px touch targets, 16px inputs (prevents iOS zoom), safe-area insets
- `< 1024px` — Tablet: single-column layout

### 9.4 Service Worker (`sw.js` — 78 lines)

| Route Pattern | Strategy | Behavior |
|---------------|----------|----------|
| `/static/*` | Cache-first | Check cache → network fallback → cache response |
| Navigation (HTML) | Network-first | Network → `/offline.html` fallback |
| API requests | Network with cache fallback | Network → cache if offline |

**Pre-cached assets:** `style.css`, `app.js`, `manifest.json`, `icon-192.png`, `icon-512.png`, `/offline.html`

**Lifecycle:** Install (pre-cache, skipWaiting) → Activate (delete old caches, claim clients) → Fetch (route-based strategies)

### 9.5 PWA Manifest

```json
{
  "name": "SocialPoster",
  "short_name": "SocialPoster",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#6366f1",
  "background_color": "#f8fafc",
  "orientation": "any",
  "icons": [
    {"src": "/static/icons/icon-192.png", "sizes": "192x192"},
    {"src": "/static/icons/icon-512.png", "sizes": "512x512"},
    {"src": "/static/icons/icon-maskable-192.png", "sizes": "192x192", "purpose": "maskable"},
    {"src": "/static/icons/icon-maskable-512.png", "sizes": "512x512", "purpose": "maskable"}
  ]
}
```

---

## 10. Mobile (Capacitor)

### 10.1 Configuration

**`capacitor.config.json`:**
```json
{
  "appId": "com.socialposter.app",
  "appName": "SocialPoster",
  "webDir": "src/socialposter/web/static",
  "server": {
    "url": "http://localhost:5000",
    "cleartext": true
  },
  "plugins": {
    "SplashScreen": {
      "backgroundColor": "#6366f1",
      "launchAutoHide": true,
      "launchShowDuration": 2000,
      "showSpinner": false
    },
    "StatusBar": {
      "style": "LIGHT",
      "backgroundColor": "#6366f1"
    }
  }
}
```

### 10.2 Capacitor Plugins

| Package | Version | Purpose |
|---------|---------|---------|
| `@capacitor/core` | ^8.2.0 | Base framework |
| `@capacitor/cli` | ^8.2.0 | Build tools |
| `@capacitor/android` | ^8.2.0 | Android runtime |
| `@capacitor/ios` | ^8.2.0 | iOS runtime |
| `@capacitor/app` | ^8.0.1 | App lifecycle, deep linking (`socialposter://`) |
| `@capacitor/camera` | ^8.0.2 | Photo capture for media upload |
| `@capacitor/splash-screen` | ^8.0.1 | Branded launch screen |
| `@capacitor/status-bar` | ^8.0.1 | Status bar styling |

### 10.3 Mobile UX Features

| Feature | Implementation |
|---------|----------------|
| Bottom Navigation | 5-tab bar (Compose, Analytics, Calendar, Inbox, Team) + floating Publish button |
| Hamburger Menu | Toggles nav on < 768px (animated spans) |
| Camera Capture | Capacitor Camera or HTML5 file input fallback |
| Safe Area Insets | `env(safe-area-inset-*)` on body, topbar, bottom bar |
| Touch Targets | 48px minimum height for all interactive elements |
| Pull-to-Refresh | Swipe down (80px threshold) → page reload |
| Deep Links | `socialposter://oauth/complete` for OAuth redirect |
| Viewport | `width=device-width, initial-scale=1.0, viewport-fit=cover` |

---

## 11. Configuration & Environment

### 11.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_APP` | Flask app module | `socialposter.web.app:create_app` |
| `SOCIALPOSTER_SECRET_KEY` | Flask secret key | `"dev-secret-change-me-in-production"` |
| `SOCIALPOSTER_ENCRYPTION_KEY` | Fernet key for token encryption | (empty — plaintext fallback) |

Generate an encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### 11.2 Database

- **Engine:** SQLite
- **Location:** `~/.socialposter/socialposter.db`
- **Max upload size:** 512 MB (`MAX_CONTENT_LENGTH`)
- **Upload directory:** `~/.socialposter/uploads/`

Uploads are saved with UUID filenames. Media type is auto-detected:
- **Video:** .mp4, .mov, .avi, .mkv, .webm, .3gp
- **Image:** .jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp
- **Document:** all others

### 11.3 Python Dependencies

**Core:**

| Package | Minimum Version | Purpose |
|---------|----------------|---------|
| `flask` | >= 3.0 | Web framework |
| `flask-login` | >= 0.6 | Session management |
| `flask-sqlalchemy` | >= 3.1 | ORM integration |
| `flask-cors` | >= 4.0 | CORS support |
| `flask-wtf` | >= 1.2 | CSRF protection |
| `flask-migrate` | >= 4.0 | Alembic migrations |
| `pydantic` | >= 2.0 | Data validation |
| `pyyaml` | >= 6.0 | YAML parsing |
| `requests` | >= 2.31 | HTTP client |
| `tweepy` | >= 4.14 | Twitter API |
| `google-api-python-client` | >= 2.100 | Google/YouTube API |
| `google-auth-oauthlib` | >= 1.0 | Google OAuth |
| `google-auth-httplib2` | >= 0.2 | Google auth HTTP |
| `apscheduler` | >= 3.10 | Background scheduling |
| `pyjwt` | >= 2.8 | JWT tokens |
| `python-dotenv` | >= 1.0 | Environment loading |
| `cryptography` | >= 42.0 | Fernet encryption |
| `rich` | >= 13.0 | Console formatting |
| `gunicorn` | >= 22.0 | Production WSGI |

**Dev:**

| Package | Minimum Version | Purpose |
|---------|----------------|---------|
| `pytest` | >= 7.0 | Testing |
| `pytest-mock` | >= 3.0 | Mocking |

---

## 12. Testing

### 12.1 Fixtures (`tests/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `app` | **Session** | Creates Flask app with in-memory SQLite (`sqlite:///:memory:`), `TESTING=True`, `WTF_CSRF_ENABLED=False`, `SECRET_KEY="test-secret-key"` |
| `db` | **Function** | Clean database session; creates all tables, yields `db`, drops all tables after test |
| `test_user` | **Function** | Admin user (`test@example.com`, password `password123`) with default team |
| `client` | **Function** | Logged-in Flask test client (session set to `test_user.id`) |
| `sample_yaml` | **Function** | Temporary `.yaml` content file with all 6 platform overrides |

**Helper:** `_add_connection(db, user_id, platform, token, extra_data)` — creates `PlatformConnection` rows for tests.

### 12.2 Test Files

| File | Tests | Coverage |
|------|-------|---------|
| `test_content.py` | 6 | YAML loading, enabled platforms, text overrides/fallbacks, text limits, nonexistent file error |
| `test_publisher.py` | 2 | Dry-run publish, empty platforms filter |
| `test_cli.py` | 5 | `--version` flag, `platforms` command, `validate` (valid + invalid), `post --dry-run` |
| `test_security.py` | 5 | Fernet roundtrip, plaintext fallback, no-key passthrough, CSRF rejection (no token), CSRF acceptance (with token) |
| `test_web_fixes.py` | 20+ | Meta disconnect (removes FB+IG+WA), WhatsApp validation (text/recipients/template), connection config save, WhatsApp recipients, YouTube tags/validation, `/api/platforms` connected status, multi-platform dry-run, override construction |
| `platforms/test_twitter.py` | 6 | Empty text, text too long, valid text, override usage, authentication (no connection / valid), publish (single + thread) |
| `platforms/test_facebook.py` | 5 | Missing page_id, empty text, valid text+page_id, authentication (no connection / valid) |

### 12.3 Key Testing Patterns

- **Session-scoped app** + **per-test db** pattern prevents cross-test contamination
- Token encryption tests reset module-level `_fernet` and `_checked` cache via `patch.dict(os.environ)`
- CSRF tests use a separate `csrf_app` fixture with CSRF enabled, extract tokens from HTML with regex
- Platform mocking: `patch("tweepy.Client")` (top-level, not import path), mock `_get_connection`
- Web tests use JSON payloads to `/api/post` with `dry_run` flag

---

## 13. Deployment

### 13.1 Prerequisites

- Python >= 3.11
- pip (or a virtualenv manager like `venv`)
- Node.js >= 18 (only needed for Capacitor mobile builds)
- A Linux/macOS server for production (Gunicorn does not run on Windows)

### 13.2 Local Development Setup

```bash
# 1. Clone the repository
git clone <repo-url> && cd socialposter

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Install the package in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Create a .env file from the example
cp .env.example .env
# Edit .env — set SOCIALPOSTER_SECRET_KEY to a random value
# Optionally set SOCIALPOSTER_ENCRYPTION_KEY (generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# )

# 5. Start the development server
socialposter serve
# → http://localhost:5000
```

### 13.3 First-Run Walkthrough

1. Navigate to `http://localhost:5000/signup`
2. Register the first account — it is **automatically promoted to admin**
3. Go to `/admin/settings` and configure:
   - **OAuth credentials** for each platform (Meta, LinkedIn, Google, Twitter)
   - **AI provider** (Claude or OpenAI) with API key
4. Go to `/connections` and connect your social accounts via OAuth
5. Return to `/` to compose and publish your first post

### 13.4 CLI Commands

The CLI is registered as a console script in `pyproject.toml`:

```toml
[project.scripts]
socialposter = "socialposter.cli:main"
```

| Command | Description |
|---------|-------------|
| `socialposter serve [--host] [--port] [--debug/--no-debug]` | Launch Flask development server (default: `0.0.0.0:5000`, debug on) |
| `socialposter post <file> [--dry-run] [--platforms P1,P2] [--user-id N]` | Publish from YAML/JSON content file |
| `socialposter validate <file>` | Validate content file without publishing |
| `socialposter platforms` | List registered platform plugins |
| `socialposter db upgrade` | Run pending Alembic migrations |
| `socialposter db downgrade` | Revert last migration |

### 13.5 Production Deployment (Linux)

#### 13.5.1 Install

```bash
# On the server
python -m venv /opt/socialposter/.venv
source /opt/socialposter/.venv/bin/activate
pip install .
```

#### 13.5.2 Environment

Create `/opt/socialposter/.env`:

```bash
FLASK_APP=socialposter.web.app:create_app
SOCIALPOSTER_SECRET_KEY=<generate-a-strong-random-key>
SOCIALPOSTER_ENCRYPTION_KEY=<generate-with-Fernet.generate_key()>
```

#### 13.5.3 Run with Gunicorn

```bash
gunicorn "socialposter.web.app:create_app()" \
  --bind 127.0.0.1:5000 \
  --workers 4 \
  --timeout 120 \
  --access-logfile /var/log/socialposter/access.log \
  --error-logfile /var/log/socialposter/error.log
```

**Worker count guideline:** `(2 × CPU cores) + 1`

#### 13.5.4 Systemd Service

Create `/etc/systemd/system/socialposter.service`:

```ini
[Unit]
Description=SocialPoster Web Application
After=network.target

[Service]
User=socialposter
Group=socialposter
WorkingDirectory=/opt/socialposter
EnvironmentFile=/opt/socialposter/.env
ExecStart=/opt/socialposter/.venv/bin/gunicorn \
  "socialposter.web.app:create_app()" \
  --bind 127.0.0.1:5000 \
  --workers 4 \
  --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable socialposter
sudo systemctl start socialposter
```

#### 13.5.5 Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name socialposter.example.com;

    client_max_body_size 512M;   # matches Flask MAX_CONTENT_LENGTH

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/socialposter/src/socialposter/web/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

For HTTPS, add a TLS certificate (e.g. via Let's Encrypt / Certbot).

#### 13.5.6 Production Checklist

| Item | Action |
|------|--------|
| Secret key | Set `SOCIALPOSTER_SECRET_KEY` to a strong random value |
| Encryption key | Set `SOCIALPOSTER_ENCRYPTION_KEY` to protect stored OAuth tokens |
| Debug mode | Ensure `--debug` is **not** passed (Gunicorn handles this) |
| HTTPS | Terminate TLS at the reverse proxy (Nginx + Certbot) |
| CORS origins | Update `create_app()` CORS origins if serving from a custom domain |
| File permissions | `~/.socialposter/` directory writable by the service user |
| Log rotation | Configure logrotate for `/var/log/socialposter/` |
| Backups | Back up `~/.socialposter/socialposter.db` regularly (SQLite) |
| Firewall | Only expose ports 80/443; block direct access to 5000 |

### 13.6 Database Migrations

Flask-Migrate (Alembic) is initialized in `create_app()`:

```python
from flask_migrate import Migrate
Migrate(app, db)
```

```bash
# Initialize migrations (first time only)
flask db init

# Generate a migration after model changes
flask db migrate -m "description of change"

# Apply pending migrations
socialposter db upgrade

# Revert last migration
socialposter db downgrade
```

The app also includes **auto-migration** logic that runs on every startup:
1. Adds `timezone` column to `users` table if missing
2. Ensures admin users have a default team membership

### 13.7 Mobile Builds (Capacitor)

#### 13.7.1 Setup

```bash
# Install Node dependencies
npm install

# Update the server URL in capacitor.config.json
# Change "url" from "http://localhost:5000" to your production URL
```

#### 13.7.2 Android

```bash
npx cap add android          # First time only
npx cap sync android         # Sync web assets + plugins
npx cap open android         # Open in Android Studio
# Build APK/AAB from Android Studio
```

#### 13.7.3 iOS

```bash
npx cap add ios              # First time only
npx cap sync ios             # Sync web assets + plugins
npx cap open ios             # Open in Xcode
# Build and archive from Xcode
```

#### 13.7.4 Mobile Production Notes

- Update `capacitor.config.json` → `server.url` to your production HTTPS URL
- Remove `"cleartext": true` (only needed for local HTTP dev)
- Configure OAuth redirect URLs to include `socialposter://oauth/complete` in each platform's developer console
- Ensure your production server's CORS config includes `capacitor://localhost`

### 13.8 Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_security.py

# Run a specific test class
pytest tests/test_web_fixes.py::TestWhatsAppValidation
```

### 13.9 Recommended Hosting Platforms

#### Key Constraints

Before choosing a host, note these architectural requirements:

| Requirement | Reason |
|-------------|--------|
| **Persistent filesystem** | SQLite database + file uploads stored on disk (`~/.socialposter/`) |
| **Long-lived process** | APScheduler runs in-process (every 30s posts, every 5min comments) |
| **Stable public URL** | OAuth callbacks require a fixed HTTPS redirect URL |
| **Python 3.11+** | Minimum runtime version |

These constraints **rule out** serverless (AWS Lambda, Vercel, Netlify) and ephemeral-filesystem platforms (Heroku free tier) since SQLite and APScheduler need a persistent, always-on server.

#### Recommended Options

##### Tier 1: VPS (Best Fit)

A traditional VPS is the best match — persistent disk, full control, long-lived processes.

| Platform | Starting Price | Why It Fits |
|----------|---------------|-------------|
| **DigitalOcean Droplet** | $6/mo (1 vCPU, 1 GB) | Simple setup, good docs, snapshots for backups |
| **Hetzner Cloud** | ~$4/mo (2 vCPU, 2 GB) | Best price/performance ratio in EU/US |
| **Linode (Akamai)** | $5/mo (1 vCPU, 1 GB) | Reliable, good network, free backups add-on |
| **AWS Lightsail** | $5/mo (1 vCPU, 512 MB) | AWS ecosystem, static IP included, predictable billing |

**Setup:** Follow Section 13.5 (systemd + Nginx + Gunicorn). A 1 GB instance handles this app well for small-to-medium teams.

##### Tier 2: PaaS with Persistent Volumes

These platforms offer managed deploys while still supporting persistent storage.

| Platform | Starting Price | Notes |
|----------|---------------|-------|
| **Fly.io** | Free tier (3 shared VMs) | Persistent volumes for SQLite, `fly deploy` from Dockerfile, auto-TLS |
| **Railway** | $5/mo (usage-based) | Git push deploys, persistent volumes, easy env vars |
| **Render** | $7/mo (starter instance) | Persistent disks ($0.25/GB), auto-deploy from GitHub, free TLS |

**Trade-off:** Simpler deploy workflow, but less control and slightly higher cost at scale.

##### Tier 3: Cloud VMs (Production / Enterprise)

| Platform | Service | Starting Price | Notes |
|----------|---------|---------------|-------|
| **Azure** | B1s VM + Azure Database for PostgreSQL Flexible Server | ~$4/mo VM + ~$13/mo DB | Managed DB, built-in backups, VNet integration, pair with Azure App Service for zero-downtime deploys |
| **AWS** | EC2 (t3.micro free tier) + RDS PostgreSQL | Free tier → ~$15/mo | Full control, Route 53 + ACM for DNS/TLS |
| **Google Cloud** | Compute Engine (e2-micro free tier) | Free tier → ~$7/mo | Good if using Google OAuth already |

**Azure Production Architecture:**

```
Azure App Service (or B1s VM + Gunicorn)
  ├── Azure Database for PostgreSQL (Flexible Server, Burstable B1ms ~$13/mo)
  ├── Azure Blob Storage (for media uploads instead of local disk)
  ├── Azure Key Vault (for SOCIALPOSTER_SECRET_KEY, ENCRYPTION_KEY, OAuth secrets)
  └── Azure Front Door or Application Gateway (TLS termination, CDN for /static/)
```

**Quick Azure VM setup:**

```bash
# Create resource group
az group create --name socialposter-rg --location eastus

# Create VM
az vm create \
  --resource-group socialposter-rg \
  --name socialposter-vm \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --admin-username azureuser \
  --generate-ssh-keys

# Open port 80/443
az vm open-port --resource-group socialposter-rg --name socialposter-vm --port 80,443

# SSH in and follow Section 13.5 (systemd + Nginx + Gunicorn)
```

#### NOT Recommended

| Platform | Reason |
|----------|--------|
| **Heroku** (free/eco) | Ephemeral filesystem — SQLite data lost on restart |
| **Vercel / Netlify** | Serverless only — no persistent process for APScheduler |
| **AWS Lambda** | No long-running process, no persistent filesystem |
| **Google Cloud Run** | Scales to zero — kills APScheduler, ephemeral disk |

#### Recommendation Summary

| Use Case | Recommendation |
|----------|---------------|
| **Solo / hobby** | Hetzner Cloud ($4/mo) or Fly.io (free tier) |
| **Small team** | DigitalOcean Droplet ($6/mo) or Railway ($5/mo) |
| **Production / enterprise** | Azure VM (B1s) + Azure Database for PostgreSQL |

#### Scaling Note: SQLite → PostgreSQL

SQLite works well for single-server deployments. For production on Azure (or any multi-worker setup), migrate to **PostgreSQL**:

```bash
# 1. Install the PostgreSQL driver
pip install psycopg2-binary

# 2. Update .env (example for Azure Database for PostgreSQL)
SQLALCHEMY_DATABASE_URI=postgresql://socialposter:YourPassword@socialposter-db.postgres.database.azure.com:5432/socialposter

# 3. Apply migrations
socialposter db upgrade
```

No application code changes needed — SQLAlchemy abstracts the database engine. Azure Database for PostgreSQL Flexible Server (Burstable B1ms, ~$13/mo) provides automated backups, high availability, and connection pooling out of the box.

---

*End of Technical Document*
