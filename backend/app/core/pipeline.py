"""End-to-end orchestration of URL -> .apkg.

Kept intentionally thin: this module contains no business logic of its own,
only sequencing and progress reporting. Each step delegates to a single-
responsibility service module, which keeps the pipeline easy to test,
reorder, or partially reuse (e.g. re-running only segmentation).
"""
from __future__ import annotations

from pathlib import Path

from app.api.schemas import GenerateRequest, JobStage
from app.config import settings
from app.core.exceptions import PipelineError
from app.core.job_manager import job_manager
from app.llm.factory import get_llm_provider
from app.logging_config import get_logger
from app.services.anki_builder import CardData, build_deck
from app.services.card_enrichment import enrich_segment
from app.services.downloader import YouTubeDownloader
from app.services.segmenter import segment_transcript
from app.services.srt_splitter import read_segment_text, split_srt_for_segment
from app.services.subtitles import normalize_to_srt, srt_to_plain_transcript
from app.services.transcriber import transcribe_to_srt
from app.services.video_cutter import cut_segment, ensure_ffmpeg_available
from app.utils.file_utils import clear_directory, slugify

logger = get_logger(__name__)


def run_pipeline(job_id: str, request: GenerateRequest) -> None:
    try:
        _run(job_id, request)
    except PipelineError as exc:
        logger.exception("Pipeline failed at stage '%s'", exc.stage)
        job_manager.update(job_id, stage=JobStage.FAILED, error=str(exc), message="Failed")
    except Exception as exc:  # noqa: BLE001 - top-level safety net for background thread
        logger.exception("Unexpected pipeline failure")
        job_manager.update(
            job_id, stage=JobStage.FAILED, error=f"Unexpected error: {exc}", message="Failed"
        )


def _run(job_id: str, request: GenerateRequest) -> None:
    settings.ensure_directories()
    ensure_ffmpeg_available()

    job_manager.update(job_id, stage=JobStage.DOWNLOADING, progress_percent=5,
                        message="Downloading video...")
    downloader = YouTubeDownloader(settings.downloads_dir, preferred_lang=request.language)
    result = downloader.download(str(request.url))

    # --- Subtitles: use existing ones, or fall back to Whisper -------------
    job_manager.update(job_id, stage=JobStage.SUBTITLES, progress_percent=25,
                        message="Checking subtitles...")
    full_srt_path = settings.subtitles_dir / f"{result.video_path.stem}.srt"

    if result.subtitle_path is not None:
        normalize_to_srt(result.subtitle_path, full_srt_path)
    else:
        job_manager.update(job_id, stage=JobStage.TRANSCRIBING, progress_percent=30,
                            message="No subtitles found, transcribing with faster-whisper "
                                    "(this may take a while)...")
        transcribe_to_srt(result.video_path, full_srt_path, language=request.language)

    transcript_text = srt_to_plain_transcript(full_srt_path)

    # --- Segmentation --------------------------------------------------
    job_manager.update(job_id, stage=JobStage.SEGMENTING, progress_percent=55,
                        message="Analyzing transcript with LLM...")
    provider = get_llm_provider(request.llm_provider)
    segments = segment_transcript(provider, transcript_text)

    # --- Cutting + per-segment SRT + enrichment -------------------------
    job_manager.update(job_id, stage=JobStage.CUTTING, progress_percent=65,
                        message=f"Cutting {len(segments)} segments...")
    cards: list[CardData] = []
    for index, segment in enumerate(segments, start=1):
        slug = f"{index:03d}-{slugify(segment.title)}"
        clip_path = settings.segments_dir / f"{slug}.mp4"
        segment_srt_path = settings.segments_dir / f"{slug}.srt"

        cut_segment(result.video_path, clip_path, segment.start_seconds, segment.end_seconds)
        split_srt_for_segment(full_srt_path, segment_srt_path, segment.start_seconds,
                               segment.end_seconds)
        segment_text = read_segment_text(segment_srt_path)

        enrichment = enrich_segment(
            provider,
            segment_text,
            include_translation=request.include_translation,
            include_pronunciation_tips=request.include_pronunciation_tips,
            translation_language=request.translation_language or "es",
        )

        cards.append(
            CardData(
                title=segment.title,
                video_path=clip_path,
                transcript=segment_text,
                translation=enrichment.translation,
                pronunciation_tip=enrichment.pronunciation_tip,
            )
        )

        progress = 65 + int((index / len(segments)) * 20)
        job_manager.update(job_id, progress_percent=progress,
                            message=f"Cut segment {index}/{len(segments)}: {segment.title}")

    # --- Build .apkg -----------------------------------------------------
    job_manager.update(job_id, stage=JobStage.BUILDING_DECK, progress_percent=88,
                        message="Building Anki deck...")
    deck_name = result.title[:60] or "YouTube Deck"
    output_path = settings.output_dir / f"{slugify(result.title)}.apkg"
    build_deck(deck_name, cards, output_path)

    # --- Cleanup -----------------------------------------------------------
    job_manager.update(job_id, stage=JobStage.CLEANING_UP, progress_percent=97,
                        message="Cleaning up temporary files...")
    if settings.cleanup_after_job:
        _cleanup_temp(settings.workdir)

    job_manager.update(
        job_id,
        stage=JobStage.DONE,
        progress_percent=100,
        message=f"Done! Deck saved with {len(cards)} cards.",
        output_file=str(output_path),
    )


def _cleanup_temp(workdir: Path) -> None:
    for subdir in ("downloads", "subtitles", "segments", "anki"):
        clear_directory(workdir / subdir)
