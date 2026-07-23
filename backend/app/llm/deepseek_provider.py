"""DeepSeek provider. DeepSeek exposes an OpenAI-compatible ``/chat/completions``
endpoint, so we reuse the official ``openai`` SDK pointed at DeepSeek's base
URL instead of writing a bespoke HTTP client."""
from __future__ import annotations

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.base import LLMProvider


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(self) -> None:
        if not settings.deepseek_api_key:
            raise LLMProviderError("DEEPSEEK_API_KEY is not set")
        self._client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=settings.deepseek_model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:
            raise LLMProviderError(f"DeepSeek request failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMProviderError("DeepSeek returned an empty response")
        return content
