"""Video + subtitle download using yt-dlp.

Design decision
----------------
``yt-dlp`` is the actively maintained fork of youtube-dl, handles YouTube's
frequent changes, and can fetch both the video stream and any
author-provided or auto-generated captions in a single pass. We drive it
through its Python API (``yt_dlp.YoutubeDL``) rather than shelling out to the
CLI, which gives us structured metadata (title, duration, available
subtitles) without scraping stdout.

Subtitle source priority (manual vs. auto-generated)
------------------------------------------------------
YouTube's auto-generated captions are known to censor profanity/slang and
contain transcription artifacts, so creator-uploaded ("manual") subtitles
are strictly preferred when both exist for the requested language.

Rather than relying on yt-dlp's internal merge behavior (passing both
``writesubtitles`` and ``writeautomaticsub`` as True and trusting it to
prefer the manual track -- which it does today, but that's an internal
implementation detail, not a documented public contract, and both file
types end up with the *same* output filename so we'd have no way to verify
after the fact which one we actually got), we make the choice explicit and
verifiable in our own code:

1. We already have full subtitle metadata from the initial ``extract_info``
   call (``info['subtitles']`` = manual, ``info['automatic_captions']`` =
   auto-generated) -- no extra network request needed.
2. We check, for the exact requested language, whether a manual track
   exists. If so, we request *only* manual subtitles from yt-dlp
   (``writeautomaticsub=False``) -- auto-generated captions for that
   language are never even considered.
3. Only if no manual track exists for that language do we fall back to
   requesting the auto-generated one.
4. If neither exists, we skip the subtitle download entirely (saves a
   request and reduces 429 risk) and the pipeline falls back to
   faster-whisper.
5. The chosen source ("manual" / "automatic" / "none") is logged explicitly
   and returned on ``DownloadResult.subtitle_source`` so it's always
   possible to verify what ended up in a given deck.

Other hardening fixes vs. the initial version:

- Subtitle language matching is exact (``[preferred_lang]``) instead of a
  wildcard (``en.*``). The wildcard used to match dozens of YouTube's
  auto-translated caption tracks (en-de, en-fr, en-ja, ...) and yt-dlp would
  try to fetch every one of them, which reliably triggers YouTube's 429
  rate limiting on longer videos.
- A subtitle-download failure (network hiccup, rate limit, etc.) no longer
  aborts the whole job. The video itself still downloads; if subtitles
  couldn't be fetched we simply return ``subtitle_path=None`` and the
  pipeline falls back to faster-whisper, exactly as if the video had no
  captions at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yt_dlp

from app.config import settings
from app.core.exceptions import DownloadError
from app.logging_config import get_logger

logger = get_logger(__name__)

SubtitleSource = Literal["manual", "automatic", "none"]


@dataclass(slots=True)
class DownloadResult:
    video_path: Path
    title: str
    duration_seconds: float
    subtitle_path: Path | None = None
    subtitle_source: SubtitleSource = "none"
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

    def _log_cookie_status(self) -> None:
        """Best-effort diagnostic run once per download.

        A misconfigured or expired cookie file currently fails silently:
        yt-dlp just falls through to YouTube's generic "sign in to confirm
        your age" error with no indication of *why* the cookies didn't
        help. This makes the real cause visible in the logs: missing file,
        zero YouTube cookies in it (wrong export), or present-but-possibly-
        expired/insufficient cookies (a YouTube/account-side issue, not a
        bug in this code).
        """
        if settings.yt_dlp_cookies_file:
            path = Path(settings.yt_dlp_cookies_file)
            if not path.exists():
                logger.error(
                    "YT_DLP_COOKIES_FILE is set to '%s' but that file does not exist. "
                    "Age-gated videos will fail until this path is fixed.",
                    path,
                )
                return
            try:
                import http.cookiejar

                jar = http.cookiejar.MozillaCookieJar(str(path))
                jar.load(ignore_discard=True, ignore_expires=True)
                yt_cookies = [c for c in jar if "youtube.com" in c.domain or "google.com" in c.domain]
                logger.info(
                    "Cookie file '%s' loaded: %d total cookies, %d for "
                    "youtube.com/google.com.",
                    path.name, len(jar), len(yt_cookies),
                )
                if not yt_cookies:
                    logger.warning(
                        "The cookie file has NO youtube.com/google.com cookies. "
                        "Age-gated videos will still fail -- re-export cookies.txt "
                        "while logged into youtube.com in that browser."
                    )
            except Exception as exc:
                logger.error(
                    "Could not parse YT_DLP_COOKIES_FILE ('%s'): %s. Age-gated "
                    "videos will fail until this is fixed.",
                    path, exc,
                )
        elif settings.yt_dlp_cookies_from_browser:
            logger.info(
                "Using cookies from browser '%s' for this request.",
                settings.yt_dlp_cookies_from_browser,
            )
        else:
            logger.info(
                "No yt-dlp cookies configured (YT_DLP_COOKIES_FILE / "
                "YT_DLP_COOKIES_FROM_BROWSER are empty). Age-gated videos will "
                "fail with 'Sign in to confirm your age'."
            )

    def download(self, url: str, skip_subtitles: bool = False) -> DownloadResult:
        output_template = str(self.output_dir / "%(id)s.%(ext)s")
        self._log_cookie_status()

        # --- Step 1: download the video itself. This also gives us full
        # subtitle metadata (both manual and automatic tracks per
        # language) for free, which we use below to decide the subtitle
        # source explicitly instead of relying on yt-dlp's internal
        # merge order. ----------------------------------------------
        video_opts = {
            **self._base_ydl_opts(),
            "format": "bestvideo*+bestaudio/best",
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

        manual_subs: dict = info.get("subtitles") or {}
        auto_subs: dict = info.get("automatic_captions") or {}
        available_langs = list(manual_subs.keys()) + list(auto_subs.keys())

        # --- Step 2: decide the subtitle source explicitly. -------------
        if skip_subtitles:
            logger.info("Skipping subtitle download (Whisper-only mode requested)")
            subtitle_path, subtitle_source = None, "none"
        elif self.preferred_lang in manual_subs:
            logger.info(
                "Manual (creator-uploaded) subtitles found for '%s' -- using these "
                "and ignoring any auto-generated track.",
                self.preferred_lang,
            )
            subtitle_path = self._try_download_subtitles(url, video_id, automatic=False)
            subtitle_source = "manual" if subtitle_path else "none"
        elif self.preferred_lang in auto_subs:
            logger.info(
                "No manual subtitles for '%s'; found auto-generated captions -- "
                "using those as fallback (note: YouTube auto-captions may censor "
                "profanity/slang and contain transcription errors).",
                self.preferred_lang,
            )
            subtitle_path = self._try_download_subtitles(url, video_id, automatic=True)
            subtitle_source = "automatic" if subtitle_path else "none"
        else:
            logger.info(
                "No subtitles (manual or automatic) available for '%s'. "
                "Will fall back to faster-whisper transcription.",
                self.preferred_lang,
            )
            subtitle_path, subtitle_source = None, "none"

        return DownloadResult(
            video_path=video_path,
            title=info.get("title", video_id),
            duration_seconds=float(info.get("duration") or 0.0),
            subtitle_path=subtitle_path,
            subtitle_source=subtitle_source,
            available_subtitle_langs=available_langs,
        )

    def _try_download_subtitles(self, url: str, video_id: str, automatic: bool) -> Path | None:
        subtitle_opts = {
            **self._base_ydl_opts(),
            "skip_download": True,
            # Explicitly request ONLY the source we already determined is
            # available, so there is no ambiguity about what gets fetched.
            "writesubtitles": not automatic,
            "writeautomaticsub": automatic,
            "subtitleslangs": [self.preferred_lang],
            "subtitlesformat": "srt/best",
            "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
        }

        try:
            with yt_dlp.YoutubeDL(subtitle_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            kind = "auto-generated" if automatic else "manual"
            logger.warning(
                "Could not fetch %s subtitles for language '%s' (%s). "
                "Falling back to faster-whisper transcription instead.",
                kind,
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