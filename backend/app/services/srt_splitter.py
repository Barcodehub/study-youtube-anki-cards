"""Slice the full-video SRT into one re-timed SRT per segment.

Each output SRT contains only the cues overlapping ``[start, end)`` and has
its timestamps shifted so the first cue begins at (approximately) 00:00:00,
matching the corresponding cut video clip.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import srt as srt_lib

from app.core.exceptions import SubtitleExtractionError
from app.logging_config import get_logger

logger = get_logger(__name__)


def split_srt_for_segment(
    full_srt_path: Path,
    destination: Path,
    start_seconds: float,
    end_seconds: float,
) -> Path:
    content = full_srt_path.read_text(encoding="utf-8")
    try:
        subtitles = list(srt_lib.parse(content))
    except Exception as exc:
        raise SubtitleExtractionError(f"Could not parse SRT for splitting: {exc}") from exc

    start_td = dt.timedelta(seconds=start_seconds)
    end_td = dt.timedelta(seconds=end_seconds)

    segment_cues = []
    for sub in subtitles:
        # Keep cues that overlap the segment window at all.
        if sub.end <= start_td or sub.start >= end_td:
            continue

        new_start = max(sub.start, start_td) - start_td
        new_end = min(sub.end, end_td) - start_td
        if new_end <= new_start:
            continue

        segment_cues.append(
            srt_lib.Subtitle(
                index=len(segment_cues) + 1,
                start=new_start,
                end=new_end,
                content=sub.content,
            )
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(srt_lib.compose(segment_cues), encoding="utf-8")
    logger.debug("Wrote %d cues -> %s", len(segment_cues), destination.name)
    return destination


def read_segment_text(srt_path: Path) -> str:
    """Plain (no timestamps) text of a segment's SRT, used for the card back."""
    content = srt_path.read_text(encoding="utf-8")
    subtitles = list(srt_lib.parse(content))
    lines = [" ".join(sub.content.split()) for sub in subtitles]
    return " ".join(line for line in lines if line)
