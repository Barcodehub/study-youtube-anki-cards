"""Optional enrichment of a card's back side: translation and pronunciation
tips (contractions, linking, reductions typical of native speech).

Kept as a separate, optional LLM call (rather than folded into the
segmentation prompt) so it can be toggled on/off per job without affecting
the more critical segmentation step, and so a failure here never aborts the
whole pipeline -- enrichment failures degrade gracefully to "no extra info".
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMProviderError
from app.llm.base import LLMProvider
from app.logging_config import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an English pronunciation and translation assistant for language "
    "learners. Respond with STRICT JSON ONLY, no markdown fences, no commentary."
)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class Enrichment(BaseModel):
    translation: str | None = None
    pronunciation_tip: str | None = None


def enrich_segment(
    provider: LLMProvider,
    english_text: str,
    include_translation: bool,
    include_pronunciation_tips: bool,
    translation_language: str = "es",
) -> Enrichment:
    if not include_translation and not include_pronunciation_tips:
        return Enrichment()

    requests = []
    if include_translation:
        requests.append(f'"translation": a natural translation into {translation_language}')
    if include_pronunciation_tips:
        requests.append(
            '"pronunciation_tip": one short, practical tip about how native '
            "speakers actually pronounce this (contractions, linking, "
            "reductions like 'gonna', 'wanna', dropped sounds, etc). "
            "Empty string if there is nothing notable."
        )

    prompt = (
        f"Text: \"{english_text}\"\n\n"
        f"Return a JSON object with these fields: {', '.join(requests)}."
    )

    try:
        raw = provider.complete(_SYSTEM_PROMPT, prompt)
        candidate = _extract_json(raw)
        data = json.loads(candidate)
        return Enrichment.model_validate(data)
    except (LLMProviderError, json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Card enrichment failed, continuing without it: %s", exc)
        return Enrichment()


def _extract_json(raw_text: str) -> str:
    text = raw_text.strip()
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx : end_idx + 1]
    return text
