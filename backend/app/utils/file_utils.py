"""Small filesystem helpers used across services."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def slugify(text: str, max_length: int = 60) -> str:
    """Turn arbitrary text into a filesystem-safe slug."""
    slug = _SLUG_RE.sub("-", text.strip()).strip("-").lower()
    return (slug or "segment")[:max_length]


def clear_directory(path: Path) -> None:
    """Remove all contents of a directory without deleting the directory
    itself (so downstream code can keep writing to the same handle)."""
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def human_readable_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
