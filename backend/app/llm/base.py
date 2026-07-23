"""Abstract LLM provider.

Design decision
----------------
We define a minimal ``LLMProvider`` protocol (a single ``complete`` method)
so ``segmenter.py`` never talks to DeepSeek / Claude / OpenAI SDKs directly.
This is the classic Strategy pattern: swapping providers is a one-line
change in ``.env`` (``LLM_PROVIDER=...``), and adding a fourth provider
later only requires implementing this interface -- no changes to business
logic. Each concrete provider is responsible for its own retry/backoff via
``tenacity`` since transient network errors differ per vendor.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Contract every LLM backend must satisfy."""

    name: str = "base"

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text completion for the given prompts.

        Implementations should request the lowest-temperature / most
        deterministic setting available, since the caller expects strict
        JSON output.
        """
        raise NotImplementedError
