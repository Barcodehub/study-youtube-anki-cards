"""Domain-specific exceptions. Keeping a small hierarchy lets the API layer
translate failures into precise HTTP responses instead of generic 500s."""
from __future__ import annotations


class PipelineError(Exception):
    """Base class for all recoverable pipeline errors."""

    stage: str = "unknown"


class DownloadError(PipelineError):
    stage = "download"


class SubtitleExtractionError(PipelineError):
    stage = "subtitles"


class TranscriptionError(PipelineError):
    stage = "transcription"


class SegmentationError(PipelineError):
    stage = "segmentation"


class VideoCuttingError(PipelineError):
    stage = "cutting"


class AnkiBuildError(PipelineError):
    stage = "anki_build"


class LLMProviderError(PipelineError):
    stage = "llm"


class JobNotFoundError(Exception):
    """Raised when a job_id does not exist in the job manager."""
