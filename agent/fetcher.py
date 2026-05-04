"""Fetch, filter, deduplicate, and rank tech and AI news stories."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from time import mktime
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests

from config import NEWSAPI_KEY


logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://hnrss.org/frontpage",
    "https://feeds.feedburner.com/TechCrunch",
    "https://www.artificialintelligence-news.com/feed/",
    "https://venturebeat.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_QUERY = "artificial intelligence OR LLM OR machine learning OR tech startup"

KEYWORDS = [
    "ai",
    "llm",
    "gpt",
    "claude",
    "gemini",
    "openai",
    "anthropic",
    "robotics",
    "chip",
    "nvidia",
    "open source",
    "startup",
    "machine learning",
    "deep learning",
    "neural",
    "model",
    "agent",
]


def fetch_stories(newsapi_key: str | None = None) -> list[dict]:
    """Fetch stories from RSS and NewsAPI, then return the top five ranked items."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    raw_stories = _fetch_rss_stories(now) + _fetch_newsapi_stories(newsapi_key or NEWSAPI_KEY, now)
    filtered = [_with_score(story, now) for story in raw_stories if _is_recent(story, cutoff)]
    filtered = [story for story in filtered if story["_keyword_count"] > 0]
    unique = _dedupe_by_url(filtered)
    ranked = sorted(unique, key=lambda story: story["_score"], reverse=True)

    stories = []
    for story in ranked[:5]:
        stories.append(
            {
                "title": story["title"],
                "url": story["url"],
                "source": story["source"],
                "published_at": story["published_at"],
                "summary": story["summary"],
            }
        )
    return stories


def _fetch_rss_stories(now: datetime) -> list[dict]:
    stories: list[dict] = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            logger.exception("Failed to parse RSS feed: %s", feed_url)
            continue

        if getattr(feed, "bozo", False):
            logger.warning("RSS feed parse warning for %s", feed_url)

        source = _get_feed_source(feed, feed_url)
        for entry in getattr(feed, "entries", []):
            story = _story_from_rss_entry(entry, source, now)
            if story:
                stories.append(story)

    logger.info("Fetched %s RSS stories", len(stories))
    return stories


def _fetch_newsapi_stories(newsapi_key: str, now: datetime) -> list[dict]:
    if not newsapi_key:
        logger.warning("NEWSAPI_KEY is not set; skipping NewsAPI source")
        return []

    params = {
        "q": NEWSAPI_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "from": (now - timedelta(hours=24)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "apiKey": newsapi_key,
    }

    try:
        response = requests.get(NEWSAPI_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("Failed to fetch NewsAPI stories")
        return []

    stories = []
    for article in payload.get("articles", []):
        title = (article.get("title") or "").strip()
        url = (article.get("url") or "").strip()
        published_at = _parse_datetime(article.get("publishedAt"), now)
        if not title or not url or not published_at:
            continue

        source = (article.get("source") or {}).get("name") or urlparse(url).netloc or "NewsAPI"
        summary = _trim_summary(article.get("description") or article.get("content") or "")
        stories.append(
            {
                "title": title,
                "url": url,
                "source": source,
                "published_at": published_at.isoformat(),
                "summary": summary,
            }
        )

    logger.info("Fetched %s NewsAPI stories", len(stories))
    return stories


def _story_from_rss_entry(entry: Any, source: str, now: datetime) -> dict | None:
    title = (_entry_get(entry, "title") or "").strip()
    url = (_entry_get(entry, "link") or "").strip()
    published_at = _entry_datetime(entry, now)
    if not title or not url or not published_at:
        return None

    summary = _trim_summary(
        _entry_get(entry, "summary")
        or _entry_get(entry, "description")
        or _entry_get(entry, "subtitle")
        or ""
    )
    return {
        "title": title,
        "url": url,
        "source": source,
        "published_at": published_at.isoformat(),
        "summary": summary,
    }


def _entry_get(entry: Any, key: str) -> Any:
    if isinstance(entry, dict):
        return entry.get(key)
    return getattr(entry, key, None)


def _get_feed_source(feed: Any, feed_url: str) -> str:
    feed_meta = getattr(feed, "feed", {}) or {}
    title = feed_meta.get("title") if isinstance(feed_meta, dict) else getattr(feed_meta, "title", "")
    return title or urlparse(feed_url).netloc or feed_url


def _entry_datetime(entry: Any, now: datetime) -> datetime | None:
    for parsed_key in ("published_parsed", "updated_parsed"):
        parsed_value = _entry_get(entry, parsed_key)
        if parsed_value:
            return datetime.fromtimestamp(mktime(parsed_value), tz=timezone.utc)

    for text_key in ("published", "updated", "created"):
        parsed = _parse_datetime(_entry_get(entry, text_key), now)
        if parsed:
            return parsed

    return None


def _parse_datetime(value: Any, now: datetime) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(str(value))
            except (TypeError, ValueError):
                return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _trim_summary(summary: str) -> str:
    return " ".join(summary.split())[:200]


def _is_recent(story: dict, cutoff: datetime) -> bool:
    published_at = _parse_datetime(story.get("published_at"), datetime.now(timezone.utc))
    return published_at is not None and published_at >= cutoff


def _with_score(story: dict, now: datetime) -> dict:
    text = f"{story.get('title', '')} {story.get('summary', '')}".lower()
    keyword_count = sum(1 for keyword in KEYWORDS if keyword in text)
    published_at = _parse_datetime(story.get("published_at"), now) or now
    age_seconds = max((now - published_at).total_seconds(), 0)
    recency_score = max(0.0, 1.0 - (age_seconds / 86400))

    scored = dict(story)
    scored["_keyword_count"] = keyword_count
    scored["_score"] = keyword_count + recency_score
    return scored


def _dedupe_by_url(stories: list[dict]) -> list[dict]:
    unique: dict[str, dict] = {}
    for story in stories:
        url = story.get("url")
        if not url:
            continue
        if url not in unique or story["_score"] > unique[url]["_score"]:
            unique[url] = story
    return list(unique.values())

