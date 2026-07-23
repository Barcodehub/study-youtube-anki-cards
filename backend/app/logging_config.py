"""Centralized logging setup. Call ``configure_logging()`` once at startup."""
from __future__ import annotations

import logging
import sys

from app.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. reload in dev mode).
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root.setLevel(level)
    root.addHandler(handler)

    # Quiet down noisy third-party loggers unless we're in DEBUG.
    if level > logging.DEBUG:
        for noisy in ("httpx", "httpcore", "faster_whisper", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
