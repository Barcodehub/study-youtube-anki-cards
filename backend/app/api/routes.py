from __future__ import annotations

import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.schemas import GenerateRequest, GenerateResponse, JobStatusResponse
from app.core.exceptions import JobNotFoundError
from app.core.job_manager import job_manager
from app.core.pipeline import run_pipeline
from app.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/jobs", response_model=GenerateResponse, status_code=202)
def create_job(request: GenerateRequest) -> GenerateResponse:
    job_id = job_manager.create_job()
    thread = threading.Thread(target=run_pipeline, args=(job_id, request), daemon=True)
    thread.start()
    logger.info("Started job %s for %s", job_id, request.url)
    return GenerateResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    try:
        job = job_manager.get(job_id)
        eta = job_manager.estimate_seconds_remaining(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    return JobStatusResponse(
        job_id=job.job_id,
        stage=job.stage,
        progress_percent=job.progress_percent,
        message=job.message,
        error=job.error,
        estimated_seconds_remaining=eta,
        output_file=job.output_file,
    )


@router.get("/jobs/{job_id}/download")
def download_deck(job_id: str) -> FileResponse:
    try:
        job = job_manager.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    if not job.output_file:
        raise HTTPException(status_code=409, detail="Job has no output yet")

    path = Path(job.output_file)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Output file no longer exists")

    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
