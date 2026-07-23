"""In-memory job tracking.

Design decision
----------------
This is a single-user local desktop app (Tauri sidecar), so a persistent
job queue (Redis/Celery) would be over-engineering. A thread-safe in-memory
dict keyed by job_id, updated from a background thread and read by the
FastAPI polling endpoint, is sufficient and keeps the dependency footprint
minimal. If multi-job history/persistence is ever needed, this class is the
single seam to swap for a SQLite-backed implementation.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from app.api.schemas import JobStage
from app.core.exceptions import JobNotFoundError


@dataclass(slots=True)
class JobState:
    job_id: str
    stage: JobStage = JobStage.QUEUED
    progress_percent: int = 0
    message: str = "Queued"
    error: str | None = None
    output_file: str | None = None
    created_at: float = field(default_factory=time.time)
    stage_started_at: float = field(default_factory=time.time)


# Rough relative weight of each stage, used to estimate remaining time.
_STAGE_WEIGHTS: dict[JobStage, int] = {
    JobStage.QUEUED: 0,
    JobStage.DOWNLOADING: 20,
    JobStage.SUBTITLES: 5,
    JobStage.TRANSCRIBING: 25,
    JobStage.SEGMENTING: 10,
    JobStage.CUTTING: 25,
    JobStage.BUILDING_DECK: 10,
    JobStage.CLEANING_UP: 5,
    JobStage.DONE: 0,
    JobStage.FAILED: 0,
}


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = JobState(job_id=job_id)
        return job_id

    def get(self, job_id: str) -> JobState:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def update(
        self,
        job_id: str,
        *,
        stage: JobStage | None = None,
        progress_percent: int | None = None,
        message: str | None = None,
        error: str | None = None,
        output_file: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            if stage is not None and stage != job.stage:
                job.stage = stage
                job.stage_started_at = time.time()
            if progress_percent is not None:
                job.progress_percent = progress_percent
            if message is not None:
                job.message = message
            if error is not None:
                job.error = error
            if output_file is not None:
                job.output_file = output_file

    def estimate_seconds_remaining(self, job_id: str) -> int | None:
        job = self.get(job_id)
        if job.stage in (JobStage.DONE, JobStage.FAILED, JobStage.QUEUED):
            return None
        remaining_weight = sum(
            weight
            for stage, weight in _STAGE_WEIGHTS.items()
            if _stage_order(stage) > _stage_order(job.stage)
        )
        # Very rough heuristic: 1 weight unit ~= 1.5 seconds. Good enough for
        # a progress hint, not a precise ETA.
        return int(remaining_weight * 1.5)


def _stage_order(stage: JobStage) -> int:
    order = list(JobStage)
    return order.index(stage)


job_manager = JobManager()
