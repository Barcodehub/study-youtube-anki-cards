"""Local speech-to-text fallback using faster-whisper.

Design decision
----------------
``faster-whisper`` (CTranslate2 backend) is used instead of the original
OpenAI ``whisper`` package: it is 4-8x faster on CPU, uses far less memory,
and supports int8 quantization out of the box -- all important since this
must run comfortably on a user's local machine, not a GPU server. The model
is only invoked when yt-dlp found no subtitles at all, per the spec.

GPU fallback
------------
With ``WHISPER_DEVICE=auto`` (the default), CTranslate2 will try to use an
NVIDIA GPU if one is detected. On Windows this frequently fails at runtime
with errors like "Library cublas64_12.dll is not found or cannot be
loaded" -- the machine has an NVIDIA driver (so a GPU is "detected") but not
the full CUDA Toolkit/cuDNN runtime libraries that CTranslate2 actually
needs to execute on it. Requiring every user to install the CUDA Toolkit
just to run this app on CPU would be a bad experience, so instead we detect
this specific class of failure at transcription time and transparently
retry once, forcing CPU + int8 quantization. This makes the app "just
work" on machines with a GPU but an incomplete/broken CUDA install, while
still using the GPU (faster) whenever it's actually usable.
"""
from __future__ import annotations

from pathlib import Path

from faster_whisper import WhisperModel

from app.config import settings
from app.core.exceptions import TranscriptionError
from app.logging_config import get_logger

logger = get_logger(__name__)

_model_cache: dict[str, WhisperModel] = {}

# Substrings that reliably indicate a GPU/CUDA runtime problem (missing
# cuBLAS/cuDNN libraries, driver mismatch, etc.) rather than a genuine
# transcription failure.
_GPU_FAILURE_HINTS = ("cublas", "cudnn", "cuda", "nvcuda", "libcu")


def _get_model(device: str, compute_type: str) -> WhisperModel:
    key = f"{settings.whisper_model_size}:{device}:{compute_type}"
    if key not in _model_cache:
        logger.info(
            "Loading faster-whisper model '%s' (device=%s, compute_type=%s)...",
            settings.whisper_model_size, device, compute_type,
        )
        _model_cache[key] = WhisperModel(
            settings.whisper_model_size,
            device=device,
            compute_type=compute_type,
        )
    return _model_cache[key]


def _is_gpu_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(hint in message for hint in _GPU_FAILURE_HINTS)


def transcribe_to_srt(audio_or_video_path: Path, destination: Path, language: str) -> Path:
    """Run faster-whisper on the given media file and write an SRT file.

    Tries the configured device first (``WHISPER_DEVICE``, default
    "auto"); if that fails with a GPU/CUDA-related runtime error, falls
    back to CPU + int8 automatically and retries once.
    """
    try:
        return _transcribe(
            audio_or_video_path, destination, language,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    except Exception as exc:
        if settings.whisper_device != "cpu" and _is_gpu_failure(exc):
            logger.warning(
                "GPU transcription failed (%s). This usually means CUDA/cuBLAS "
                "runtime libraries aren't installed, even though a GPU was "
                "detected. Retrying on CPU instead...",
                exc,
            )
            try:
                return _transcribe(
                    audio_or_video_path, destination, language,
                    device="cpu", compute_type="int8",
                )
            except Exception as cpu_exc:
                raise TranscriptionError(
                    f"faster-whisper transcription failed on both GPU and CPU: {cpu_exc}"
                ) from cpu_exc
        raise TranscriptionError(f"faster-whisper transcription failed: {exc}") from exc


def _transcribe(
    audio_or_video_path: Path, destination: Path, language: str, device: str, compute_type: str
) -> Path:
    model = _get_model(device, compute_type)
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


def _fmt(total_seconds: float) -> str:
    ms = round(total_seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"