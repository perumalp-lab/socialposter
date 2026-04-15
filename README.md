# SocialPoster

**Post content to 6 social platforms with one command.**

Write your content in a YAML file, run `socialposter post content.yaml`, and it gets published to LinkedIn, YouTube, Instagram, Facebook, X (Twitter), and WhatsApp.

## Quick Start

```bash
# Install
cd socialposter
pip install -e .

# Configure a platform (interactive)
socialposter config set linkedin
socialposter config set twitter

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
| `socialposter config set <platform>` | Interactive credential setup |
| `socialposter config list` | Show all platform status |
| `socialposter config test` | Test connectivity |
| `socialposter platforms` | List available plugins |
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
3. Set redirect URL: `http://127.0.0.1:8585/callback`
4. Run: `socialposter config set linkedin`

### X (Twitter)
1. Create app at https://developer.x.com/
2. Generate Consumer Keys + Access Tokens
3. Ensure Read+Write permissions
4. Run: `socialposter config set twitter`

### Facebook
1. Create app at https://developers.facebook.com/
2. Get Page Access Token via Graph API Explorer
3. Required: `pages_manage_posts` permission (requires App Review)
4. Run: `socialposter config set facebook`

### YouTube
1. Create project at https://console.cloud.google.com/
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `client_secrets.json`
5. Run: `socialposter config set youtube`

### Instagram
1. Convert to Business Account connected to a Facebook Page
2. Create Meta app with `instagram_content_publish` permission
3. Get long-lived access token
4. Run: `socialposter config set instagram`
5. Set `business_account_id` in `~/.socialposter/config.yaml`

### WhatsApp
1. Set up WhatsApp Business on Meta Developer portal
2. Get System User Access Token
3. Run: `socialposter config set whatsapp`
4. Set `phone_number_id` in `~/.socialposter/config.yaml`

## Architecture

```
src/socialposter/
├── cli/            # Typer commands (post, config, validate)
├── core/           # Content parser, config, credentials, publisher
├── platforms/      # Plugin for each platform (LinkedIn, X, etc.)
└── utils/          # OAuth helper, retry, logging
```

**Key design patterns:**
- **Plugin architecture** – Each platform is a self-contained class registered via decorator
- **Content merging** – Defaults + per-platform overrides in a single YAML file
- **Parallel publishing** – Platforms are posted to concurrently via ThreadPoolExecutor
- **Secure credentials** – OS keyring (Windows Credential Locker) with env var fallback

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
