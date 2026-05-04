"""Entry point for the AI News Agent."""

from __future__ import annotations

import logging
import sys

from agent import dedup, fetcher, generator, sender
from config import validate_config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    try:
        try:
            validate_config()
        except RuntimeError as exc:
            logger.error("%s", exc)
            return 1

        stories = fetcher.fetch_stories()
        if not stories:
            logger.info("No new stories today")
            return 0

        stories = dedup.filter_seen(stories)
        if not stories:
            logger.info("All stories already sent")
            return 0

        post_dict = generator.generate_post(stories)
        sender.send_to_telegram(post_dict)
        dedup.mark_sent(post_dict["share_link"])
        logger.info("Success: posted story '%s'", post_dict.get("story_title", "unknown"))
        return 0
    except SystemExit as exc:
        raise exc
    except Exception:
        logger.exception("Unhandled error while running AI News Agent")
        return 1


if __name__ == "__main__":
    sys.exit(main())
