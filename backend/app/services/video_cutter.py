"""Frame-accurate video cutting via FFmpeg.

Design decision
----------------
We shell out to the ``ffmpeg`` binary via ``subprocess`` rather than a
Python FFmpeg wrapper library. FFmpeg's CLI is the stable, documented
interface; thin wrapper libraries (ffmpeg-python, moviepy) add an
abstraction layer that lags behind FFmpeg's own flags and pulls in extra
dependencies (moviepy in particular drags in numpy/imageio and is far
heavier than needed here). We re-encode (rather than ``-c copy``) because
stream-copy cuts snap to the nearest keyframe, which is not accurate enough
for language-learning clips that must start/end exactly where the
transcript says.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.core.exceptions import VideoCuttingError
from app.logging_config import get_logger

logger = get_logger(__name__)


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise VideoCuttingError(
            "ffmpeg was not found on PATH. Please install FFmpeg and make sure "
            "it is accessible from the command line."
        )


def cut_segment(
    source_video: Path,
    destination: Path,
    start_seconds: float,
    end_seconds: float,
) -> Path:
    """Cut ``[start_seconds, end_seconds)`` from ``source_video`` into
    ``destination`` with frame-accurate re-encoding, normalized for Anki
    playback (H.264 + AAC, yuv420p for broad compatibility)."""
    duration = max(end_seconds - start_seconds, 0.05)
    destination.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start_seconds:.3f}",
        "-i", str(source_video),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(destination),
    ]

    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise VideoCuttingError(
            f"ffmpeg failed to cut segment ({destination.name}): {result.stderr[-1000:]}"
        )

    return destination
