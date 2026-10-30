# backend/app/ai_client.py: ai_client module.
"""OpenRouter chat client - Cloud AI (the only working AI option, spec 12).

Server-side only: the OpenRouter key never leaves backend/.env. Responses
and failures never log document content, tokens, or keys - only HTTP
status codes. No fallback model: if this provider fails, the caller gets
a clear, safe error and the locker keeps working without the assistant.
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
                                                                            
TIMEOUT = (5.0, 90.0)


class ProviderError(Exception):
    """Provider unavailable/busy/malformed. Messages are always safe to show."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def _unavailable() -> ProviderError:
    return ProviderError("The AI provider is unavailable. Please try again later.")


def chat(system: str, user: str, *, max_tokens: int | None = None) -> str:
    """One-shot completion. Returns the assistant text or raises ProviderError."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ProviderError("AI is not configured on this server.")

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens or settings.ai_max_output_tokens,
        "reasoning": {"effort": settings.openrouter_reasoning_effort},
    }

    try:
        response = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=TIMEOUT,
        )
    except httpx.HTTPError:
        raise _unavailable() from None

    if response.status_code == 429:
        raise ProviderError("The AI provider is busy. Please try again shortly.")
    if response.status_code >= 400:
        logger.warning("OpenRouter returned HTTP %s", response.status_code)
        raise _unavailable()

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        logger.warning("OpenRouter returned an unexpected payload shape")
        raise ProviderError(
            "The AI provider returned an unexpected response."
        ) from None
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("The AI provider returned an empty response.")
    return content.strip()
