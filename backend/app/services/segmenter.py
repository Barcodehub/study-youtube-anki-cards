"""Semantic segmentation via LLM.

Design decision
----------------
We ask the LLM for JSON-only output and validate it through a Pydantic
model (`SegmentList`) rather than trusting it blindly. LLMs occasionally
wrap JSON in markdown fences or add stray commentary despite instructions,
so we strip fences defensively before parsing. If validation fails we retry
once with an explicit correction prompt before giving up -- this is far
more robust than a single best-effort parse.
"""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.api.schemas import Segment, SegmentList
from app.config import settings
from app.core.exceptions import SegmentationError
from app.llm.base import LLMProvider
from app.logging_config import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are an expert linguistic content editor who prepares \
video transcripts for language-learning flashcards. You divide a transcript \
into semantic segments and respond with STRICT JSON ONLY: no markdown \
fences, no commentary, no explanations -- just a JSON array."""

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _build_user_prompt(transcript: str, min_seconds: int, max_seconds: int) -> str:
    return f"""Below is a timestamped transcript of a video, using the format
[start --> end] text per line.

Split it into semantic segments where each segment represents ONE complete
idea (a greeting, a full explanation, a complete example, a full exchange in
a dialogue, etc). Rules:
- NEVER cut in the middle of a sentence, a dialogue turn, an explanation, or
  an example.
- Each segment should last approximately between {min_seconds} and
  {max_seconds} seconds, but a complete idea takes priority over the exact
  duration if there is a conflict.
- Segments must be contiguous and in chronological order. The end of one
  segment does not need to exactly equal the start of the next, but there
  should be no large unexplained gaps.
- Use the exact timestamp format HH:MM:SS.mmm for "start" and "end".
- Give each segment a short, descriptive "title" (max 6 words).

Respond with ONLY a JSON array, formatted exactly like this example:
[
  {{"title": "Greeting", "start": "00:00:00.000", "end": "00:00:36.200"}},
  {{"title": "Ordering Coffee", "start": "00:00:36.200", "end": "00:01:18.900"}}
]

Transcript:
{transcript}
"""


def _extract_json_array(raw_text: str) -> str:
    text = raw_text.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        return fence_match.group(1).strip()

    # Fallback: grab the substring between the first '[' and the last ']'.
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx : end_idx + 1]
    return text


def _parse_segments(raw_text: str) -> list[Segment]:
    candidate = _extract_json_array(raw_text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise SegmentationError(f"LLM did not return valid JSON: {exc}") from exc

    try:
        parsed = SegmentList.model_validate({"segments": data})
    except ValidationError as exc:
        raise SegmentationError(f"LLM JSON failed schema validation: {exc}") from exc

    if not parsed.segments:
        raise SegmentationError("LLM returned an empty segment list")

    return parsed.segments


def segment_transcript(
    provider: LLMProvider,
    transcript: str,
    min_seconds: int | None = None,
    max_seconds: int | None = None,
) -> list[Segment]:
    """Call the LLM and return validated, chronologically sorted segments."""
    min_s = min_seconds or settings.segment_min_seconds
    max_s = max_seconds or settings.segment_max_seconds
    prompt = _build_user_prompt(transcript, min_s, max_s)

    raw_response = provider.complete(_SYSTEM_PROMPT, prompt)

    try:
        segments = _parse_segments(raw_response)
    except SegmentationError:
        logger.warning("First segmentation attempt failed validation, retrying once...")
        correction_prompt = (
            prompt
            + "\n\nIMPORTANT: your previous response was not valid JSON matching "
            "the required schema. Respond again with ONLY a valid JSON array, "
            "no other text."
        )
        raw_response = provider.complete(_SYSTEM_PROMPT, correction_prompt)
        segments = _parse_segments(raw_response)

    segments.sort(key=lambda s: s.start_seconds)

    # Discard degenerate zero/negative-length segments defensively.
    valid_segments = [s for s in segments if s.duration_seconds > 0]
    if not valid_segments:
        raise SegmentationError("No valid (positive-duration) segments were produced")

    logger.info("LLM produced %d valid segments", len(valid_segments))
    return valid_segments
