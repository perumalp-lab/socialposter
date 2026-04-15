"""OAuth blueprint – connect/callback/disconnect for each platform."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from flask import Blueprint, flash, redirect, request, session, url_for
from flask_login import current_user, login_required

from socialposter.web.models import AppSetting, PlatformConnection, db

oauth_bp = Blueprint("oauth", __name__, url_prefix="/oauth")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redirect_uri(platform: str) -> str:
    return url_for("oauth.callback", platform=platform, _external=True)


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    verifier = secrets.token_urlsafe(64)
    challenge = hashlib.sha256(verifier.encode("ascii")).digest()
    import base64
    challenge_b64 = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode("ascii")
    return verifier, challenge_b64


def _oauth_complete_redirect():
    """Redirect to mobile deep link or web connections page after OAuth."""
    if session.pop("oauth_source_mobile", False):
        return redirect("socialposter://oauth/complete")
    return redirect(url_for("main.connections"))


def _validate_oauth_callback(platform_label: str):
    """Common preamble for OAuth callbacks.

    Checks for error query-params, validates the ``state`` parameter, and
    reads the ``code``, ``client_id``, and ``client_secret`` settings.

    Returns ``(code, client_id, client_secret)`` on success, or a
    ``redirect`` Response on failure.
    """
    if request.args.get("error"):
        desc = request.args.get("error_description") or request.args.get("error", "")
        flash(f"{platform_label} authorization denied: {desc}", "error")
        return redirect(url_for("main.connections"))

    state = request.args.get("state")
    if state != session.pop("oauth_state", None):
        flash("Invalid OAuth state.", "error")
        return redirect(url_for("main.connections"))

    code = request.args.get("code")
    return code


def _save_connection(user_id, platform, access_token, refresh_token=None,
                     expires_in=None, extra_data=None):
    """Upsert a PlatformConnection."""
    conn = PlatformConnection.query.filter_by(
        user_id=user_id, platform=platform
    ).first()

    expires_at = None
    if expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    if conn:
        conn.access_token = access_token
        conn.refresh_token = refresh_token or conn.refresh_token
        conn.token_expires_at = expires_at
        if extra_data:
            conn.extra_data = {**(conn.extra_data or {}), **extra_data}
        conn.connected_at = datetime.now(timezone.utc)
    else:
        conn = PlatformConnection(
            user_id=user_id,
            platform=platform,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
            extra_data=extra_data,
        )
        db.session.add(conn)

    db.session.commit()


# ---------------------------------------------------------------------------
# Generic entry points
# ---------------------------------------------------------------------------

@oauth_bp.route("/<platform>/connect")
@login_required
def connect(platform: str):
    """Redirect user to the platform's OAuth consent screen."""
    # Track mobile source for post-OAuth redirect
    if request.args.get("source") == "mobile":
        session["oauth_source_mobile"] = True

    handler = _CONNECT_HANDLERS.get(platform)
    if not handler:
        flash(f"Unknown platform: {platform}", "error")
        return redirect(url_for("main.connections"))
    return handler()


@oauth_bp.route("/<platform>/callback")
@login_required
def callback(platform: str):
    """Handle the OAuth callback from the platform."""
    handler = _CALLBACK_HANDLERS.get(platform)
    if not handler:
        flash(f"Unknown platform: {platform}", "error")
        return redirect(url_for("main.connections"))
    return handler()


@oauth_bp.route("/<platform>/disconnect", methods=["POST"])
@login_required
def disconnect(platform: str):
    """Remove a platform connection.

    Meta platforms (facebook, instagram, whatsapp) are connected together,
    so disconnecting one removes all three.
    """
    meta_platforms = {"facebook", "instagram", "whatsapp", "meta"}
    if platform in meta_platforms:
        # Disconnect all Meta-linked platforms together
        conns = PlatformConnection.query.filter(
            PlatformConnection.user_id == current_user.id,
            PlatformConnection.platform.in_(["facebook", "instagram", "whatsapp"]),
        ).all()
        for conn in conns:
            db.session.delete(conn)
        if conns:
            db.session.commit()
            flash("Disconnected from Meta (Facebook, Instagram, WhatsApp).", "success")
    else:
        conn = PlatformConnection.query.filter_by(
            user_id=current_user.id, platform=platform
        ).first()
        if conn:
            db.session.delete(conn)
            db.session.commit()
            flash(f"Disconnected from {platform}.", "success")
    return redirect(url_for("main.connections"))


# ===================================================================
# META (Facebook + Instagram + WhatsApp)
# ===================================================================

def _connect_meta():
    client_id = AppSetting.get("meta_client_id")
    if not client_id:
        flash("Admin has not configured Meta OAuth credentials.", "error")
        return redirect(url_for("main.connections"))

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("meta"),
        "state": state,
        "scope": "pages_manage_posts,pages_read_engagement,instagram_basic,instagram_content_publish,whatsapp_business_messaging",
        "response_type": "code",
    }
    return redirect("https://www.facebook.com/v19.0/dialog/oauth?" + urlencode(params))


def _callback_meta():
    result = _validate_oauth_callback("Meta")
    if not isinstance(result, str):
        return result
    code = result
    client_id = AppSetting.get("meta_client_id")
    client_secret = AppSetting.get("meta_client_secret")

    # Exchange code for short-lived token
    resp = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": _redirect_uri("meta"),
            "code": code,
        },
        timeout=15,
    )
    if not resp.ok:
        flash("Failed to exchange Meta authorization code.", "error")
        return redirect(url_for("main.connections"))

    data = resp.json()
    short_token = data["access_token"]

    # Exchange for long-lived user token
    resp2 = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    long_token = resp2.json().get("access_token", short_token) if resp2.ok else short_token

    # Get user pages
    pages_resp = requests.get(
        "https://graph.facebook.com/v19.0/me/accounts",
        params={"access_token": long_token},
        timeout=15,
    )
    extra = {}
    page_token = long_token
    if pages_resp.ok:
        pages = pages_resp.json().get("data", [])
        if pages:
            page = pages[0]
            extra["page_id"] = page["id"]
            extra["page_name"] = page.get("name", "")
            page_token = page["access_token"]  # never-expiring page token

    # Save Facebook connection (with page token)
    _save_connection(
        current_user.id, "facebook", page_token,
        extra_data=extra,
    )

    # Discover Instagram Business Account
    if extra.get("page_id"):
        ig_resp = requests.get(
            f"https://graph.facebook.com/v19.0/{extra['page_id']}",
            params={"fields": "instagram_business_account", "access_token": page_token},
            timeout=15,
        )
        if ig_resp.ok:
            ig_data = ig_resp.json()
            ig_account = ig_data.get("instagram_business_account", {})
            if ig_account.get("id"):
                _save_connection(
                    current_user.id, "instagram", page_token,
                    extra_data={"business_account_id": ig_account["id"]},
                )

    # Save WhatsApp connection (same token, user configures phone_number_id in admin)
    _save_connection(
        current_user.id, "whatsapp", long_token,
        extra_data=extra,
    )

    flash("Meta platforms connected (Facebook, Instagram, WhatsApp).", "success")
    return _oauth_complete_redirect()


# ===================================================================
# LINKEDIN
# ===================================================================

def _connect_linkedin():
    client_id = AppSetting.get("linkedin_client_id")
    if not client_id:
        flash("Admin has not configured LinkedIn OAuth credentials.", "error")
        return redirect(url_for("main.connections"))

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _redirect_uri("linkedin"),
        "scope": "openid profile w_member_social",
        "state": state,
    }
    return redirect("https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params))


def _callback_linkedin():
    result = _validate_oauth_callback("LinkedIn")
    if not isinstance(result, str):
        return result
    code = result
    client_id = AppSetting.get("linkedin_client_id")
    client_secret = AppSetting.get("linkedin_client_secret")

    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri("linkedin"),
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    if not resp.ok:
        flash("Failed to exchange LinkedIn authorization code.", "error")
        return redirect(url_for("main.connections"))

    data = resp.json()
    _save_connection(
        current_user.id, "linkedin",
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in", 5184000),
    )
    flash("LinkedIn connected.", "success")
    return _oauth_complete_redirect()


# ===================================================================
# YOUTUBE (Google OAuth 2.0)
# ===================================================================

def _connect_youtube():
    client_id = AppSetting.get("google_client_id")
    if not client_id:
        flash("Admin has not configured Google OAuth credentials.", "error")
        return redirect(url_for("main.connections"))

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("youtube"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


def _callback_youtube():
    result = _validate_oauth_callback("Google")
    if not isinstance(result, str):
        return result
    code = result
    client_id = AppSetting.get("google_client_id")
    client_secret = AppSetting.get("google_client_secret")

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri("youtube"),
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    if not resp.ok:
        flash("Failed to exchange Google authorization code.", "error")
        return redirect(url_for("main.connections"))

    data = resp.json()
    _save_connection(
        current_user.id, "youtube",
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in", 3600),
    )
    flash("YouTube connected.", "success")
    return _oauth_complete_redirect()


# ===================================================================
# TWITTER/X (OAuth 2.0 + PKCE)
# ===================================================================

def _connect_twitter():
    client_id = AppSetting.get("twitter_client_id")
    if not client_id:
        flash("Admin has not configured Twitter/X OAuth credentials.", "error")
        return redirect(url_for("main.connections"))

    state = secrets.token_urlsafe(32)
    verifier, challenge = _generate_pkce()
    session["oauth_state"] = state
    session["pkce_verifier"] = verifier

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _redirect_uri("twitter"),
        "scope": "tweet.read tweet.write users.read offline.access",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect("https://twitter.com/i/oauth2/authorize?" + urlencode(params))


def _callback_twitter():
    result = _validate_oauth_callback("Twitter")
    if not isinstance(result, str):
        return result
    code = result
    verifier = session.pop("pkce_verifier", "")
    client_id = AppSetting.get("twitter_client_id")
    client_secret = AppSetting.get("twitter_client_secret")

    resp = requests.post(
        "https://api.twitter.com/2/oauth2/token",
        auth=(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri("twitter"),
            "code_verifier": verifier,
        },
        timeout=15,
    )
    if not resp.ok:
        flash("Failed to exchange Twitter authorization code.", "error")
        return redirect(url_for("main.connections"))

    data = resp.json()
    _save_connection(
        current_user.id, "twitter",
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in", 7200),
        extra_data={"auth_type": "oauth2"},
    )
    flash("Twitter/X connected.", "success")
    return _oauth_complete_redirect()


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

_CONNECT_HANDLERS = {
    "meta": _connect_meta,
    "facebook": _connect_meta,
    "instagram": _connect_meta,
    "whatsapp": _connect_meta,
    "linkedin": _connect_linkedin,
    "youtube": _connect_youtube,
    "twitter": _connect_twitter,
}

_CALLBACK_HANDLERS = {
    "meta": _callback_meta,
    "facebook": _callback_meta,
    "instagram": _callback_meta,
    "whatsapp": _callback_meta,
    "linkedin": _callback_linkedin,
    "youtube": _callback_youtube,
    "twitter": _callback_twitter,
}
