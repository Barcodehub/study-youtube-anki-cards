"""Conversions between ``HH:MM:SS.mmm`` timestamps and float seconds.

Both the LLM segmentation output and FFmpeg use this timestamp format, so
centralizing the parsing avoids subtle off-by-one / rounding bugs scattered
across modules.
"""
from __future__ import annotations

import re

_TS_RE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?:[.,](?P<ms>\d{1,3}))?$"
)


def timestamp_to_seconds(timestamp: str) -> float:
    """Parse ``HH:MM:SS.mmm`` (or ``HH:MM:SS,mmm``) into seconds (float)."""
    match = _TS_RE.match(timestamp.strip())
    if not match:
        raise ValueError(f"Invalid timestamp format: {timestamp!r}")

    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    ms_str = match.group("ms") or "0"
    milliseconds = int(ms_str.ljust(3, "0")[:3])

    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def seconds_to_timestamp(total_seconds: float, comma: bool = False) -> str:
    """Format seconds (float) as ``HH:MM:SS.mmm`` (or ``,mmm`` for SRT)."""
    if total_seconds < 0:
        total_seconds = 0.0

    total_ms = round(total_seconds * 1000)
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    seconds, milliseconds = divmod(remainder_ms, 1000)

    sep = "," if comma else "."
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{sep}{milliseconds:03d}"
