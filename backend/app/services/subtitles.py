"""Subtitle normalization.

Design decision
----------------
``pysubs2`` reads/writes virtually every subtitle format (SRT, VTT, ASS...)
with a single unified API, so we use it to normalize whatever yt-dlp
downloaded (often ``.vtt`` for auto-captions) into clean ``.srt``. We use the
lighter ``srt`` library only for the final, already-clean SRT we hand off to
the LLM as plain transcript text, since it is a tiny, well-tested
line-parser well suited for that narrower job.
"""
from __future__ import annotations

from pathlib import Path

import pysubs2
import srt as srt_lib

from app.core.exceptions import SubtitleExtractionError
from app.logging_config import get_logger

logger = get_logger(__name__)


def normalize_to_srt(subtitle_path: Path, destination: Path) -> Path:
    """Convert any subtitle file pysubs2 understands into a clean .srt."""
    try:
        subs = pysubs2.load(str(subtitle_path), encoding="utf-8")
    except Exception as exc:  # pysubs2 raises various format-specific errors
        raise SubtitleExtractionError(f"Could not parse subtitle file: {exc}") from exc

    # Auto-generated YouTube captions frequently contain duplicated /
    # overlapping cue text (word-by-word karaoke style). Deduplicate
    # consecutive identical lines to keep the transcript readable.
    deduped = []
    last_text = None
    for event in subs:
        text = event.plaintext.strip()
        if not text or text == last_text:
            continue
        deduped.append(event)
        last_text = text
    subs.events = deduped

    destination.parent.mkdir(parents=True, exist_ok=True)
    subs.save(str(destination), format_="srt")
    logger.info("Normalized subtitles -> %s (%d cues)", destination.name, len(subs))
    return destination


def srt_to_plain_transcript(srt_path: Path) -> str:
    """Produce a timestamped plain-text transcript for the LLM prompt.

    Format: ``[start --> end] text`` per line, using the same HH:MM:SS.mmm
    convention the LLM is asked to return, so it can copy timestamps
    directly instead of re-deriving them.
    """
    content = srt_path.read_text(encoding="utf-8")
    try:
        subtitles = list(srt_lib.parse(content))
    except Exception as exc:
        raise SubtitleExtractionError(f"Could not parse SRT for transcript: {exc}") from exc

    lines = []
    for sub in subtitles:
        start = _timedelta_to_ts(sub.start)
        end = _timedelta_to_ts(sub.end)
        text = " ".join(sub.content.split())
        if text:
            lines.append(f"[{start} --> {end}] {text}")
    return "\n".join(lines)


def _timedelta_to_ts(td) -> str:  # type: ignore[no-untyped-def]
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int(round((total_seconds - int(total_seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
