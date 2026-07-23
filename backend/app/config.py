"""
Centralized application configuration.

Design decision
----------------
We use ``pydantic-settings`` instead of hand-rolled ``os.environ`` parsing.
It gives us: typed fields, automatic ``.env`` loading, validation errors at
startup (fail fast) instead of obscure runtime errors, and a single source
of truth that every module imports (``from app.config import settings``).
This is the de-facto standard for FastAPI projects and avoids reinventing a
config loader.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OPENAI = "openai"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    # Paths
    workdir: Path = Path("./temp")
    output_dir: Path = Path("./output")

    # Whisper
    whisper_model_size: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    # LLM provider selection
    llm_provider: LLMProvider = LLMProvider.DEEPSEEK

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Segmentation heuristics
    segment_min_seconds: int = 20
    segment_max_seconds: int = 90

    default_language: str = "en"

    cleanup_after_job: bool = True

    # yt-dlp cookies (needed for age-gated / "confirm your age" videos).
    # Set ONE of these in .env:
    #   YT_DLP_COOKIES_FROM_BROWSER=chrome   (chrome, firefox, edge, brave, ...)
    #   YT_DLP_COOKIES_FILE=/absolute/path/to/cookies.txt
    yt_dlp_cookies_from_browser: str = ""
    yt_dlp_cookies_file: str = ""

    @property
    def downloads_dir(self) -> Path:
        return self.workdir / "downloads"

    @property
    def subtitles_dir(self) -> Path:
        return self.workdir / "subtitles"

    @property
    def segments_dir(self) -> Path:
        return self.workdir / "segments"

    @property
    def anki_media_dir(self) -> Path:
        return self.workdir / "anki"

    def ensure_directories(self) -> None:
        for path in (
            self.workdir,
            self.downloads_dir,
            self.subtitles_dir,
            self.segments_dir,
            self.anki_media_dir,
            self.output_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()