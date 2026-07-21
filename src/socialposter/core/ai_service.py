"""AI content generation service — supports Claude (Anthropic) and OpenAI."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import requests

from socialposter.web.models import AppSetting

log = logging.getLogger("socialposter")

# ── Tone guidance per platform ──

PLATFORM_TONES: dict[str, str] = {
    "linkedin": (
        "Professional and insightful. Use a confident, polished tone suited for "
        "a business audience. Keep paragraphs short. Max ~3000 characters."
    ),
    "twitter": (
        "Punchy, concise, and conversational. Must be under 280 characters. "
        "Use short sentences, be direct, and hook the reader immediately."
    ),
    "facebook": (
        "Friendly and engaging. Write for a broad audience. Use a warm, "
        "approachable tone. Encourage interaction. Up to ~63 000 characters."
    ),
    "instagram": (
        "Visual-first storytelling. Write a compelling caption that complements "
        "an image or video. Use line breaks for readability. Max ~2200 characters."
    ),
    "youtube": (
        "Informative and keyword-rich. Write a compelling video description that "
        "helps with search discovery. Max ~5000 characters."
    ),
    "whatsapp": (
        "Personal and direct, like a message to a friend or customer. "
        "Keep it brief and actionable. Max ~4096 characters."
    ),
}


# ── Provider abstraction ──

class AIProvider(ABC):
    """Base class for AI providers."""

    @abstractmethod
    def chat(self, system: str, user: str) -> str:
        """Send a system + user message and return the assistant reply."""


class ClaudeProvider(AIProvider):
    """Anthropic Messages API via requests."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929", temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def chat(self, system: str, user: str) -> str:
        resp = requests.post(
            self.API_URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "temperature": self.temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


class OpenAIProvider(AIProvider):
    """OpenAI Chat Completions API via requests."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "gpt-4o", temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def chat(self, system: str, user: str) -> str:
        resp = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class GeminiProvider(AIProvider):
    """Google Gemini API via requests."""

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def chat(self, system: str, user: str) -> str:
        url = self.API_URL.format(model=self.model)
        resp = requests.post(
            url,
            params={"key": self.api_key},
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": 1024,
                },
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


class PerplexityProvider(AIProvider):
    """Perplexity API (OpenAI-compatible) via requests."""

    API_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(self, api_key: str, model: str = "sonar", temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def chat(self, system: str, user: str) -> str:
        resp = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ── Provider registry ──

_PROVIDER_CLASSES: dict[str, type[AIProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "perplexity": PerplexityProvider,
}


_COST_TIER_RANK = {"low": 0, "standard": 1, "premium": 2}


def _pick_cheapest_workspace_model(provider_name: str) -> str | None:
    """Return the cheapest model_id for a workspace provider config, or None."""
    try:
        from socialposter.web.models import AIProviderConfig
        pc = AIProviderConfig.query.filter_by(
            name=provider_name, is_active=True
        ).first()
        if not pc or not pc.models:
            return None
        ranked = sorted(
            pc.models,
            key=lambda m: _COST_TIER_RANK.get(m.cost_tier, 1),
        )
        return ranked[0].model_id if ranked else None
    except Exception:
        return None


def _cost_optimization_enabled() -> bool:
    return (AppSetting.get("ai_cost_optimization") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def get_provider(
    provider_name: str | None = None,
    model_id: str | None = None,
    temperature: float | None = None,
    user_id: int | None = None,
) -> AIProvider:
    """Resolve and return an AI provider instance.

    Resolution order for the API key, given a provider_name:
    1. The current user's UserAIKey row for this provider (if user_id given).
    2. The workspace AIProviderConfig row (database-driven).
    3. The legacy AppSetting for that provider.

    If provider_name is None, prefer the user's default UserAIKey, then
    AppSetting's ai_provider, then fall back to "claude".
    """
    # Determine effective provider when not specified.
    if not provider_name and user_id is not None:
        try:
            from socialposter.web.models import UserAIKey
            uk = UserAIKey.query.filter_by(user_id=user_id, is_default=True).first()
            if uk and uk.api_key:
                provider_name = uk.provider
        except Exception:
            pass
    if not provider_name:
        provider_name = AppSetting.get("ai_provider", "claude")

    cls = _PROVIDER_CLASSES.get(provider_name, ClaudeProvider)
    # When cost optimization is on AND the caller didn't pin a model, route
    # to the cheapest workspace-configured model for this provider.
    cost_route = model_id is None and _cost_optimization_enabled()

    # 1) User-specific key first.
    if user_id is not None:
        try:
            from socialposter.web.models import UserAIKey
            uk = UserAIKey.query.filter_by(
                user_id=user_id, provider=provider_name
            ).first()
            if uk and uk.api_key:
                kwargs: dict = {"api_key": uk.api_key}
                if model_id:
                    kwargs["model"] = model_id
                elif cost_route:
                    cheapest = _pick_cheapest_workspace_model(provider_name)
                    if cheapest:
                        kwargs["model"] = cheapest
                    elif uk.default_model:
                        kwargs["model"] = uk.default_model
                elif uk.default_model:
                    kwargs["model"] = uk.default_model
                if temperature is not None:
                    kwargs["temperature"] = temperature
                return cls(**kwargs)
        except Exception:
            pass

    # 2) Workspace AIProviderConfig.
    try:
        from socialposter.web.models import AIProviderConfig, AIModelConfig
        pc = AIProviderConfig.query.filter_by(name=provider_name, is_active=True).first()
        if pc and pc.api_key:
            kwargs = {"api_key": pc.api_key}
            if model_id:
                kwargs["model"] = model_id
            elif pc.models:
                if cost_route:
                    ranked = sorted(
                        pc.models,
                        key=lambda m: _COST_TIER_RANK.get(m.cost_tier, 1),
                    )
                    chosen = ranked[0]
                else:
                    chosen = next(
                        (m for m in pc.models if m.is_default), None,
                    ) or pc.models[0]
                if chosen:
                    kwargs["model"] = chosen.model_id
            if temperature is not None:
                kwargs["temperature"] = temperature
            return cls(**kwargs)
    except Exception:
        pass

    # Legacy AppSetting fallback
    key_map = {
        "claude": "ai_claude_api_key",
        "openai": "ai_openai_api_key",
        "gemini": "ai_gemini_api_key",
        "perplexity": "ai_perplexity_api_key",
    }
    setting_key = key_map.get(provider_name, "ai_claude_api_key")
    api_key = AppSetting.get(setting_key)
    if not api_key:
        raise ValueError(
            f"{provider_name.title()} API key is not configured. "
            "Add your own key in Settings, or ask an admin to configure it."
        )

    kwargs = {"api_key": api_key}
    if model_id:
        kwargs["model"] = model_id
    if temperature is not None:
        kwargs["temperature"] = temperature
    return cls(**kwargs)


# ── High-level functions ──

def generate_content(
    topic: str,
    platforms: list[str],
    provider_name: str | None = None,
    model_id: str | None = None,
    temperature: float | None = None,
    user_id: int | None = None,
) -> str:
    """Generate a social media post from a topic."""
    provider = get_provider(provider_name, model_id, temperature, user_id=user_id)
    platform_list = ", ".join(platforms) if platforms else "general social media"
    system = (
        "You are a social media content writer. Write an engaging post about "
        "the given topic. Return ONLY the post text, no commentary or quotes."
    )
    user = (
        f"Write a social media post about: {topic}\n"
        f"Target platforms: {platform_list}\n"
        "Keep it engaging, concise, and ready to publish."
    )
    return provider.chat(system, user).strip()


def optimize_for_platforms(
    text: str,
    platforms: list[str],
    provider_name: str | None = None,
    model_id: str | None = None,
    temperature: float | None = None,
    user_id: int | None = None,
) -> dict[str, str]:
    """Rewrite text optimized for each platform's tone and limits."""
    provider = get_provider(provider_name, model_id, temperature, user_id=user_id)
    tones = {p: PLATFORM_TONES.get(p, "General social media tone.") for p in platforms}
    tone_descriptions = "\n".join(
        f"- {p}: {desc}" for p, desc in tones.items()
    )
    system = (
        "You are a social media optimization expert. Rewrite the given text for "
        "each platform, respecting its tone and character limits. "
        "Return ONLY valid JSON: {\"platform_name\": \"optimized text\", ...}. "
        "No markdown fences, no commentary."
    )
    user = (
        f"Original text:\n{text}\n\n"
        f"Platforms and their tone guidelines:\n{tone_descriptions}\n\n"
        "Rewrite the text for each platform listed above."
    )
    raw = provider.chat(system, user).strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("AI returned non-JSON for optimize: %s", raw[:200])
        # Fallback: return original text for each platform
        result = {p: text for p in platforms}
    return result


def generate_structured_content(
    topic: str,
    platforms: list[str],
    audience: str = "",
    goal: str = "",
    tone: str = "",
    provider_name: str | None = None,
    model_id: str | None = None,
    temperature: float | None = None,
    user_id: int | None = None,
) -> dict:
    """Generate structured content: caption, hashtags, image idea, CTA."""
    provider = get_provider(provider_name, model_id, temperature, user_id=user_id)
    platform_list = ", ".join(platforms) if platforms else "general social media"
    audience_str = f"\nTarget audience: {audience}" if audience else ""
    goal_str = f"\nGoal: {goal}" if goal else ""
    tone_str = f"\nTone: {tone}" if tone else ""

    system = (
        "You are an expert social media content strategist. Given a topic and context, "
        "produce structured content. Return ONLY valid JSON with these keys:\n"
        '  "caption": string (the main post text, engaging and ready to publish),\n'
        '  "hashtags": array of strings (5-8 relevant hashtags with # prefix),\n'
        '  "image_idea": string (a brief description of an ideal image/visual),\n'
        '  "cta": string (a short call-to-action)\n'
        "No markdown fences, no commentary."
    )
    user = (
        f"Topic: {topic}\n"
        f"Platforms: {platform_list}"
        f"{audience_str}{goal_str}{tone_str}\n"
        "Generate structured social media content."
    )
    raw = provider.chat(system, user).strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("AI returned non-JSON for structured content: %s", raw[:200])
        result = {
            "caption": raw,
            "hashtags": [],
            "image_idea": "",
            "cta": "",
        }
    return result


def suggest_reply(
    comment_text: str,
    author_name: str = "",
    platform: str = "",
    post_text: str = "",
    tone: str = "friendly",
    provider_name: str | None = None,
    model_id: str | None = None,
    temperature: float | None = None,
    user_id: int | None = None,
) -> str:
    """Draft a reply to a social comment in the requested tone."""
    provider = get_provider(provider_name, model_id, temperature, user_id=user_id)
    platform_hint = f" on {platform}" if platform else ""
    author_hint = f" from {author_name}" if author_name else ""
    post_context = f"\n\nOriginal post text:\n{post_text}" if post_text else ""

    system = (
        "You are a brand's community manager. Draft a single short reply to a "
        "social media comment. Be helpful, specific, and on-brand. Match the "
        f"requested tone: {tone}. Keep it under 280 characters. Return ONLY the "
        "reply text — no quotes, no commentary, no preamble."
    )
    user = (
        f"Comment{author_hint}{platform_hint}:\n{comment_text}{post_context}\n\n"
        "Draft the reply now."
    )
    return provider.chat(system, user).strip().strip('"').strip("'")


def suggest_hashtags(
    text: str,
    platform: str,
    count: int = 5,
    provider_name: str | None = None,
    model_id: str | None = None,
    temperature: float | None = None,
    user_id: int | None = None,
) -> list[str]:
    """Suggest hashtags for a given text and platform."""
    provider = get_provider(provider_name, model_id, temperature, user_id=user_id)
    system = (
        "You are a social media hashtag expert. Suggest relevant, trending hashtags. "
        "Return ONLY a JSON array of strings, e.g. [\"#hashtag1\", \"#hashtag2\"]. "
        "No markdown fences, no commentary."
    )
    user = (
        f"Suggest {count} hashtags for this {platform} post:\n{text}"
    )
    raw = provider.chat(system, user).strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        tags = json.loads(raw)
        if isinstance(tags, list):
            return [str(t) for t in tags[:count]]
    except json.JSONDecodeError:
        log.warning("AI returned non-JSON for hashtags: %s", raw[:200])
    # Fallback: try to extract hashtags from raw text
    return [w for w in raw.split() if w.startswith("#")][:count]
