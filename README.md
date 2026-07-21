# SocialPoster

**Post content to 6 social platforms with one command.**

Write your content in a YAML file, run `socialposter post content.yaml`, and it gets published to LinkedIn, YouTube, Instagram, Facebook, X (Twitter), and WhatsApp.

## Quick Start

```bash
# Install
cd socialposter
pip install -e .

# Start the server and connect platforms via the web UI at http://localhost:5000
socialposter serve

# Write your content
cp templates/sample_post.yaml my_post.yaml
# Edit my_post.yaml with your content...

# Validate without posting
socialposter post my_post.yaml --dry-run

# Post for real
socialposter post my_post.yaml
```

## Commands

| Command | Description |
|---------|-------------|
| `socialposter post <file>` | Publish content to platforms |
| `socialposter post <file> --dry-run` | Validate without publishing |
| `socialposter post <file> --platforms linkedin,twitter` | Post to specific platforms |
| `socialposter validate <file>` | Check content file for errors |
| `socialposter platforms` | List available plugins |
| `socialposter serve` | Launch the web UI (default command) |
| `socialposter db upgrade` | Run pending database migrations |
| `socialposter db downgrade` | Revert the last migration |
| `socialposter worker` | Start an RQ worker for scheduled jobs |
| `socialposter --version` | Show version |

## Content File Format (YAML)

```yaml
version: "1.0"

defaults:
  text: "Your post text here. Applied to all platforms unless overridden."
  media:
    - path: ./images/banner.jpg
      type: image

platforms:
  linkedin:
    enabled: true
    text: "Custom LinkedIn text (overrides default)"
  twitter:
    enabled: true
    text: "Short tweet text"
    thread:
      - "Thread reply 1"
      - "Thread reply 2"
  facebook:
    enabled: true
    page_id: "YOUR_PAGE_ID"
    link: "https://example.com"
  youtube:
    enabled: true
    title: "Video Title"
    description: "Video description"
    tags: ["tag1", "tag2"]
    privacy: public
    media:
      - path: ./videos/demo.mp4
        type: video
  instagram:
    enabled: true
    post_type: feed  # feed, reel, story, carousel
    media:
      - path: https://your-host.com/image.jpg  # Must be public URL
        type: image
  whatsapp:
    enabled: true
    recipients: ["+1234567890"]
    template_name: "greeting"
```

## Platform Setup

### LinkedIn
1. Create app at https://developer.linkedin.com/
2. Request Community Management API access
3. Set redirect URL to `http://localhost:5000/oauth/linkedin/callback` (adjust host/port to match your deployment)
4. An admin sets `linkedin_client_id` and `linkedin_client_secret` in the web UI's admin settings
5. Users connect their LinkedIn account via the web UI at `/connections`

### X (Twitter)
1. Create app at https://developer.x.com/
2. Generate OAuth 2.0 Client ID and Client Secret
3. Enable OAuth 2.0 with PKCE; set redirect URL to your server
4. Ensure Read+Write permissions
5. An admin sets `twitter_client_id` and `twitter_client_secret` in the admin settings
6. Users connect via the web UI at `/connections`

### Facebook
1. Create app at https://developers.facebook.com/
2. An admin sets `meta_client_id` and `meta_client_secret` in the admin settings
3. Users connect via the web UI (handles Facebook, Instagram, and WhatsApp in one OAuth flow)

### YouTube
1. Create project at https://console.cloud.google.com/
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Web application)
4. An admin sets `google_client_id` and `google_client_secret` in the admin settings
5. Users connect via the web UI at `/connections`

### Instagram
1. Convert to Business Account connected to a Facebook Page
2. No separate setup — Instagram is connected as part of the Meta OAuth flow (Facebook page)
3. The `business_account_id` is discovered automatically during OAuth

### WhatsApp
1. Set up WhatsApp Business on Meta Developer portal
2. No separate setup — WhatsApp is connected as part of the Meta OAuth flow
3. An admin sets the `phone_number_id` in the admin settings if needed

## Architecture

```
src/socialposter/
├── cli.py          # Click commands (serve, post, validate, platforms, db, worker)
├── core/           # Content parser, publisher, media, scheduler, AI service, plans
├── platforms/      # Plugin for each platform (LinkedIn, X, etc.)
├── web/            # Flask web app (routes, templates, models, OAuth, admin)
└── utils/          # Logger, retry, crypto, datetime helpers, pagination
```

**Key design patterns:**
- **Plugin architecture** – Each platform is a self-contained class registered via decorator
- **Content merging** – Defaults + per-platform overrides in a single YAML file
- **Parallel publishing** – Platforms are posted to concurrently via ThreadPoolExecutor
- **Secure credentials** – OAuth tokens encrypted at rest (Fernet) with DB storage and env var fallback

## Platform Limits

| Platform | Free Tier | Max Text | Media |
|----------|-----------|----------|-------|
| LinkedIn | Unlimited | 3,000 chars | Image, Video |
| X/Twitter | 500 posts/mo | 280 chars | Image, Video, GIF |
| Facebook | Unlimited (Pages) | 63,206 chars | Image, Video, Link |
| YouTube | ~6 uploads/day | 5,000 chars (desc) | Video only |
| Instagram | 25 posts/day | 2,200 chars | Image (JPEG), Reel |
| WhatsApp | 1k convos/mo | 4,096 chars | Image, Video, Doc |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a specific test
pytest tests/test_content.py -v
```

## License

MIT
