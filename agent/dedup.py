"""Deduplication helpers backed by data/seen_stories.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from config import SEEN_STORIES_PATH


logger = logging.getLogger(__name__)
MAX_SEEN_URLS = 500


def _ensure_seen_file(path: Path = SEEN_STORIES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")


def load_seen(path: Path = SEEN_STORIES_PATH) -> list[str]:
    """Load seen story URLs, creating the file if needed."""
    _ensure_seen_file(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.error("Invalid JSON in %s; resetting seen stories", path)
        data = []

    if not isinstance(data, list):
        logger.error("Expected a list in %s; resetting seen stories", path)
        return []

    return [url for url in data if isinstance(url, str)]


def save_seen(urls: Iterable[str], path: Path = SEEN_STORIES_PATH) -> None:
    """Persist seen URLs, keeping only the most recent MAX_SEEN_URLS."""
    _ensure_seen_file(path)
    trimmed = list(urls)[-MAX_SEEN_URLS:]
    path.write_text(json.dumps(trimmed, indent=2) + "\n", encoding="utf-8")


def filter_seen(stories: list[dict]) -> list[dict]:
    """Remove stories whose URL is already in seen_stories.json."""
    seen = set(load_seen())
    return [story for story in stories if story.get("url") not in seen]


def mark_sent(url: str) -> None:
    """Append a sent story URL to seen_stories.json."""
    if not url:
        logger.warning("Skipping empty URL in mark_sent")
        return

    seen = load_seen()
    if url not in seen:
        seen.append(url)
    save_seen(seen)

