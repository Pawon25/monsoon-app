"""
Thin wrapper around the Anthropic Claude API.

Centralizes: client construction, error handling/translation into
`ClaudeServiceError`, and JSON-extraction for endpoints that expect
structured output (checklist, alerts).
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.config import get_settings

logger = logging.getLogger("monsoon_app.claude")


class ClaudeServiceError(Exception):
    """Raised when the Claude API call fails or returns unusable output."""


def _client() -> anthropic.AsyncAnthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ClaudeServiceError("Claude API key not configured on server.")
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def generate_text(system: str, user: str, max_tokens: int = 800) -> str:
    """Call Claude and return the plain-text response."""
    settings = get_settings()
    client = _client()
    try:
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as exc:
        logger.error("Claude API error: %s", exc)
        raise ClaudeServiceError("The AI service is temporarily unavailable. Please try again shortly.") from exc
    except Exception as exc:  # noqa: BLE001 - guard against unexpected SDK errors
        logger.exception("Unexpected error calling Claude")
        raise ClaudeServiceError("Unexpected error generating content.") from exc

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ClaudeServiceError("The AI service returned an empty response.")
    return "\n".join(text_blocks).strip()


async def generate_json(system: str, user: str, max_tokens: int = 1200) -> Any:
    """Call Claude expecting a raw JSON response and parse it defensively."""
    raw = await generate_text(system, user, max_tokens=max_tokens)
    cleaned = raw.strip()

    # Defensive cleanup in case the model wraps output in markdown fences
    # despite instructions not to.
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude JSON output: %s | raw=%s", exc, raw[:500])
        raise ClaudeServiceError("The AI service returned an unexpected format.") from exc
