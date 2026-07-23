"""Anthropic Claude provider, using the official ``anthropic`` SDK."""
from __future__ import annotations

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.base import LLMProvider


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                temperature=0.1,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            raise LLMProviderError(f"Claude request failed: {exc}") from exc

        text_blocks = [block.text for block in response.content if block.type == "text"]
        if not text_blocks:
            raise LLMProviderError("Claude returned no text content")
        return "".join(text_blocks)
