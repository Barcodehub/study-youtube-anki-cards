"""Video + subtitle download using yt-dlp.

Design decision
----------------
``yt-dlp`` is the actively maintained fork of youtube-dl, handles YouTube's
frequent changes, and can fetch both the video stream and any
author-provided or auto-generated captions in a single pass. We drive it
through its Python API (``yt_dlp.YoutubeDL``) rather than shelling out to the
CLI, which gives us structured metadata (title, duration, available
subtitles) without scraping stdout.

Two hardening fixes vs. the initial version:

1. Subtitle language matching is now exact (``[preferred_lang]``) instead of
   a wildcard (``en.*``). The wildcard used to match dozens of YouTube's
   auto-translated caption tracks (en-de, en-fr, en-ja, ...) and yt-dlp would
   try to fetch every one of them, which reliably triggers YouTube's 429
   rate limiting on longer videos. We only want the one language the user
   asked for.
2. A subtitle-download failure (network hiccup, rate limit, etc.) no longer
   aborts the whole job. The video itself still downloads; if subtitles
   couldn't be fetched we simply return ``subtitle_path=None`` and the
   pipeline falls back to faster-whisper, exactly as if the video had no
   captions at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

from app.config import settings
from app.core.exceptions import DownloadError
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class DownloadResult:
    video_path: Path
    title: str
    duration_seconds: float
    subtitle_path: Path | None = None
    available_subtitle_langs: list[str] = field(default_factory=list)


class YouTubeDownloader:
    """Thin, typed wrapper around yt-dlp for a single video."""

    def __init__(self, output_dir: Path, preferred_lang: str = "en") -> None:
        self.output_dir = output_dir
        self.preferred_lang = preferred_lang

    def _base_ydl_opts(self) -> dict:
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 3,
            # Be a little gentler with YouTube to avoid 429s on long videos
            # with many caption tracks / large formats.
            "sleep_interval_requests": 1,
        }

        # --- Age-gated / "confirm your age" videos ---------------------
        # yt-dlp cannot bypass YouTube's age verification wall without
        # cookies from a browser session that is logged into an
        # age-verified Google account. Configure ONE of these in .env:
        #   YT_DLP_COOKIES_FROM_BROWSER=chrome   (or firefox, edge, brave...)
        #   YT_DLP_COOKIES_FILE=/path/to/cookies.txt
        if settings.yt_dlp_cookies_from_browser:
            opts["cookiesfrombrowser"] = (settings.yt_dlp_cookies_from_browser,)
        elif settings.yt_dlp_cookies_file:
            opts["cookiefile"] = settings.yt_dlp_cookies_file

        return opts

    def download(self, url: str) -> DownloadResult:
        output_template = str(self.output_dir / "%(id)s.%(ext)s")

        # --- Step 1: download the video itself (subtitles are best-effort
        # and handled separately below so a subtitle failure never aborts
        # the whole job). ----------------------------------------------
        video_opts = {
            **self._base_ydl_opts(),
            # No restringimos por contenedor (ext=mp4): pedimos el mejor
            # video + mejor audio disponibles, sea cual sea el codec/
            # contenedor original (webm/vp9, etc). ``merge_output_format``
            # se encarga de remuxear/reencodar a mp4 al final, así que el
            # resultado siempre es .mp4 aunque el origen no lo sea.
            "format": "bestvideo*+bestaudio/best",
            "verbose": True,
            "quiet": False,
            "no_warnings": False,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
        }

        try:
            with yt_dlp.YoutubeDL(video_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:  # pragma: no cover - network
            raise DownloadError(f"Failed to download video: {exc}") from exc

        if info is None:
            raise DownloadError("yt-dlp returned no metadata for this URL")

        video_id = info["id"]
        video_path = self._locate_downloaded_video(video_id)
        if video_path is None:
            raise DownloadError("Video file was not found after download")

        available_langs = list((info.get("subtitles") or {}).keys()) + list(
            (info.get("automatic_captions") or {}).keys()
        )

        # --- Step 2: try to fetch subtitles for the exact requested
        # language only. If this fails for any reason (429, no captions in
        # that language, etc.) we log it and continue without subtitles --
        # the pipeline will fall back to faster-whisper. -----------------
        subtitle_path = self._try_download_subtitles(url, video_id)

        return DownloadResult(
            video_path=video_path,
            title=info.get("title", video_id),
            duration_seconds=float(info.get("duration") or 0.0),
            subtitle_path=subtitle_path,
            available_subtitle_langs=available_langs,
        )

    def _try_download_subtitles(self, url: str, video_id: str) -> Path | None:
        subtitle_opts = {
            **self._base_ydl_opts(),
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            # Exact language only -- no wildcard. Avoids fetching every
            # auto-translated variant YouTube offers.
            "subtitleslangs": [self.preferred_lang],
            "subtitlesformat": "srt/best",
            "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
        }

        try:
            with yt_dlp.YoutubeDL(subtitle_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            logger.warning(
                "Could not fetch subtitles for language '%s' (%s). "
                "Falling back to faster-whisper transcription instead.",
                self.preferred_lang,
                exc,
            )
            return None

        return self._locate_subtitle_file(video_id)

    def _locate_downloaded_video(self, video_id: str) -> Path | None:
        for candidate in self.output_dir.glob(f"{video_id}.*"):
            if candidate.suffix.lower() in {".mp4", ".mkv", ".webm"}:
                return candidate
        return None

    def _locate_subtitle_file(self, video_id: str) -> Path | None:
        # yt-dlp names subs like ``<id>.<lang>.srt`` (or .vtt if srt unavailable).
        candidates = sorted(self.output_dir.glob(f"{video_id}.*.srt")) or sorted(
            self.output_dir.glob(f"{video_id}.*.vtt")
        )
        if not candidates:
            return None
        chosen = candidates[0]
        logger.info("Found existing subtitles: %s", chosen.name)
        return chosen