"""Pydantic models shared by the API layer and internal pipeline."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.config import LLMProvider
from app.utils.time_utils import timestamp_to_seconds


class Segment(BaseModel):
    """One semantic segment as returned by the LLM."""

    title: str = Field(min_length=1, max_length=120)
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _validate_timestamp(cls, value: str) -> str:
        # Raises ValueError (caught by pydantic) if malformed.
        timestamp_to_seconds(value)
        return value

    @property
    def start_seconds(self) -> float:
        return timestamp_to_seconds(self.start)

    @property
    def end_seconds(self) -> float:
        return timestamp_to_seconds(self.end)

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


class SegmentList(BaseModel):
    """Wrapper so we can validate the whole array atomically."""

    segments: list[Segment]


class JobStage(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    SUBTITLES = "subtitles"
    TRANSCRIBING = "transcribing"
    SEGMENTING = "segmenting"
    CUTTING = "cutting"
    BUILDING_DECK = "building_deck"
    CLEANING_UP = "cleaning_up"
    DONE = "done"
    FAILED = "failed"


class GenerateRequest(BaseModel):
    url: HttpUrl
    language: str = "en"
    llm_provider: LLMProvider | None = None
    include_translation: bool = False
    translation_language: str | None = "es"
    include_pronunciation_tips: bool = True


class JobStatusResponse(BaseModel):
    job_id: str
    stage: JobStage
    progress_percent: int = Field(ge=0, le=100)
    message: str
    error: str | None = None
    estimated_seconds_remaining: int | None = None
    output_file: str | None = None


class GenerateResponse(BaseModel):
    job_id: str
