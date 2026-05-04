"""Entry point for the AI News Agent."""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

from agent import dedup, fetcher, generator, sender
from config import validate_config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    try:
        validate_config()

        stories = fetcher.fetch_stories()
        _validate_stories(stories)
        if not stories:
            logger.info("No new stories today")
            return 0

        stories = dedup.filter_seen(stories)
        _validate_stories(stories)
        if not stories:
            logger.info("All stories already sent")
            return 0

        post_dict = generator.generate_post(stories)
        _validate_post_dict(post_dict)
        sender.send_to_telegram(post_dict)
        dedup.mark_sent(post_dict["share_link"])
        logger.info("Success: posted story '%s'", post_dict.get("story_title", "unknown"))
        return 0
    except SystemExit as exc:
        raise exc
    except Exception as exc:
        logger.exception("Unhandled error while running AI News Agent")
        _notify_failure(exc)
        return 1


def _validate_stories(stories: Any) -> None:
    if not isinstance(stories, list):
        raise ValueError("fetch_stories() must return a list")

    required = {"title", "url", "source", "published_at", "summary"}
    for index, story in enumerate(stories, start=1):
        if not isinstance(story, dict):
            raise ValueError(f"Story #{index} is not a dict")

        missing = [key for key in required if key not in story]
        if missing:
            raise ValueError(f"Story #{index} is missing required fields: {', '.join(missing)}")

        empty_required = [key for key in ("title", "url", "source", "published_at") if not story.get(key)]
        if empty_required:
            raise ValueError(f"Story #{index} has empty required fields: {', '.join(empty_required)}")


def _validate_post_dict(post_dict: Any) -> None:
    if not isinstance(post_dict, dict):
        raise ValueError("generate_post() must return a dict")

    required = {"post", "replies", "share_link", "references", "story_title"}
    missing = [key for key in required if key not in post_dict]
    if missing:
        raise ValueError(f"Generated post is missing required fields: {', '.join(sorted(missing))}")

    if not str(post_dict.get("post", "")).strip():
        raise ValueError("Generated post text is empty")
    if not str(post_dict.get("share_link", "")).strip():
        raise ValueError("Generated share_link is empty")
    if len(str(post_dict["post"])) > 280:
        raise ValueError("Generated main post exceeds 280 characters")
    if not isinstance(post_dict.get("replies"), list):
        raise ValueError("Generated replies must be a list")
    if not isinstance(post_dict.get("references"), list):
        raise ValueError("Generated references must be a list")


def _notify_failure(exc: Exception) -> None:
    if isinstance(exc, sender.TelegramSendError):
        logger.error("Skipping Telegram error notification because Telegram delivery failed")
        return

    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    notified = sender.send_error_to_telegram(type(exc).__name__, details)
    if not notified:
        logger.error("Could not notify Telegram about the failure")


if __name__ == "__main__":
    sys.exit(main())
