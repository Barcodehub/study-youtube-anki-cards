"""Local speech-to-text fallback using faster-whisper.

Design decision
----------------
``faster-whisper`` (CTranslate2 backend) is used instead of the original
OpenAI ``whisper`` package: it is 4-8x faster on CPU, uses far less memory,
and supports int8 quantization out of the box -- all important since this
must run comfortably on a user's local machine, not a GPU server. The model
is only invoked when yt-dlp found no subtitles at all, per the spec.
"""
from __future__ import annotations

from pathlib import Path

from faster_whisper import WhisperModel

from app.config import settings
from app.core.exceptions import TranscriptionError
from app.logging_config import get_logger

logger = get_logger(__name__)

_model_cache: dict[str, WhisperModel] = {}


def _get_model() -> WhisperModel:
    key = f"{settings.whisper_model_size}:{settings.whisper_device}:{settings.whisper_compute_type}"
    if key not in _model_cache:
        logger.info("Loading faster-whisper model '%s'...", settings.whisper_model_size)
        _model_cache[key] = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model_cache[key]


def transcribe_to_srt(audio_or_video_path: Path, destination: Path, language: str) -> Path:
    """Run faster-whisper on the given media file and write an SRT file."""
    try:
        model = _get_model()
        segments, _info = model.transcribe(
            str(audio_or_video_path),
            language=language if language != "auto" else None,
            vad_filter=True,
            beam_size=5,
        )

        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as fh:
            for index, segment in enumerate(segments, start=1):
                fh.write(f"{index}\n")
                fh.write(f"{_fmt(segment.start)} --> {_fmt(segment.end)}\n")
                fh.write(f"{segment.text.strip()}\n\n")

        logger.info("Whisper transcription written -> %s", destination.name)
        return destination
    except Exception as exc:
        raise TranscriptionError(f"faster-whisper transcription failed: {exc}") from exc


def _fmt(total_seconds: float) -> str:
    ms = round(total_seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
