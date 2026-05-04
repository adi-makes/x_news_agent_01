"""Telegram delivery for generated news posts."""

from __future__ import annotations

import logging
import sys

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


logger = logging.getLogger(__name__)
TELEGRAM_API_BASE = "https://api.telegram.org"


def send_to_telegram(
    post_dict: dict,
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> None:
    """Send a formatted post to Telegram using sendMessage."""
    token = bot_token or TELEGRAM_BOT_TOKEN
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    endpoint = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    message = format_telegram_message(post_dict)

    payload = {
        "chat_id": target_chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()
        body = response.json()
    except Exception:
        logger.exception("Failed to send Telegram message")
        sys.exit(1)

    if not body.get("ok", False):
        logger.error("Telegram API returned an error: %s", body)
        sys.exit(1)

    logger.info("Telegram message sent successfully")


def format_telegram_message(post_dict: dict) -> str:
    """Build the Telegram Markdown message."""
    replies = [reply for reply in post_dict.get("replies", []) if reply]
    references = [ref for ref in post_dict.get("references", []) if ref]
    reference_lines = "\n".join(f"• {ref}" for ref in references)

    parts = [
        "🗞 *AI & Tech Daily*",
        "",
        str(post_dict.get("post", "")).strip(),
    ]

    if replies:
        parts.extend(["", "\n\n".join(str(reply).strip() for reply in replies)])

    parts.extend(
        [
            "",
            f"🔗 *Share this:* {post_dict.get('share_link', '')}",
            "",
            "📚 *References:*",
            reference_lines,
            "",
            "_Posted by AI News Agent_",
        ]
    )

    return "\n".join(parts).strip()
