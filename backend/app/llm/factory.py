"""Factory that instantiates the configured LLM provider (Strategy pattern)."""
from __future__ import annotations

from app.config import LLMProvider as LLMProviderName
from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.base import LLMProvider
from app.llm.claude_provider import ClaudeProvider
from app.llm.deepseek_provider import DeepSeekProvider
from app.llm.openai_provider import OpenAIProvider

_PROVIDERS: dict[LLMProviderName, type[LLMProvider]] = {
    LLMProviderName.DEEPSEEK: DeepSeekProvider,
    LLMProviderName.CLAUDE: ClaudeProvider,
    LLMProviderName.OPENAI: OpenAIProvider,
}


def get_llm_provider(provider_name: LLMProviderName | None = None) -> LLMProvider:
    name = provider_name or settings.llm_provider
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise LLMProviderError(f"Unknown LLM provider: {name}")
    return provider_cls()
