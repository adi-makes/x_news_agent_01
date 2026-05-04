"""Telegram delivery for generated news posts."""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


logger = logging.getLogger(__name__)
TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_TELEGRAM_MESSAGE_LENGTH = 4096
TELEGRAM_TIMEOUT_SECONDS = 20


class TelegramSendError(RuntimeError):
    """Raised when Telegram delivery fails."""


def send_to_telegram(
    post_dict: dict,
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> None:
    """Send a formatted post to Telegram using sendMessage."""
    message = format_telegram_message(post_dict)
    _send_message(message, bot_token=bot_token, chat_id=chat_id, parse_mode="HTML")
    logger.info("Telegram message sent successfully")


def send_error_to_telegram(
    title: str,
    details: str,
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send a failure notification to Telegram without raising on failure."""
    try:
        _send_message(
            format_error_message(title, details),
            bot_token=bot_token,
            chat_id=chat_id,
            parse_mode="HTML",
        )
    except TelegramSendError:
        logger.exception("Failed to send Telegram error notification")
        return False

    logger.info("Telegram error notification sent successfully")
    return True


def _send_message(
    message: str,
    bot_token: str | None = None,
    chat_id: str | None = None,
    parse_mode: str | None = "HTML",
) -> None:
    """Send a raw Telegram message, raising TelegramSendError on failure."""
    token = bot_token or TELEGRAM_BOT_TOKEN
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    _validate_telegram_settings(token, target_chat_id)

    endpoint = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    text = _truncate_message(message)

    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "disable_web_page_preview": False,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    error: TelegramSendError | None = None
    try:
        _post_to_telegram(endpoint, payload)
        return
    except requests.RequestException as exc:
        raise TelegramSendError(f"Telegram HTTP request failed: {_sanitize_error_text(exc)}") from exc
    except TelegramSendError as exc:
        error = exc

    if not parse_mode or not _should_retry_plain_text(error):
        raise error

    logger.warning("Telegram rejected formatted message; retrying as plain text: %s", error)
    plain_payload = {
        "chat_id": target_chat_id,
        "text": _truncate_message(_html_to_plain_text(text)),
        "disable_web_page_preview": False,
    }
    try:
        _post_to_telegram(endpoint, plain_payload)
    except requests.RequestException as exc:
        raise TelegramSendError(f"Telegram HTTP request failed: {_sanitize_error_text(exc)}") from exc
    except TelegramSendError as retry_error:
        raise TelegramSendError(f"{error}; plain-text retry also failed: {retry_error}") from retry_error


def _post_to_telegram(endpoint: str, payload: dict[str, Any]) -> None:
    response = requests.post(endpoint, json=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
    body = _response_json(response)
    if response.status_code >= 400 or not body.get("ok", False):
        raise TelegramSendError(_telegram_error_message(response, body))


def format_telegram_message(post_dict: dict) -> str:
    """Build the Telegram HTML message."""
    replies = [_escape_html(reply) for reply in post_dict.get("replies", []) if reply]
    references = [_escape_html(ref) for ref in post_dict.get("references", []) if ref]
    share_link = _escape_html(post_dict.get("share_link", ""))
    reference_lines = "\n".join(f"• {ref}" for ref in references)

    parts = [
        "🗞 <b>AI &amp; Tech Daily</b>",
        "",
        _escape_html(post_dict.get("post", "")),
    ]

    if replies:
        parts.extend(["", "\n\n".join(replies)])

    parts.extend(
        [
            "",
            f"🔗 <b>Share this:</b> {share_link}",
            "",
            "📚 <b>References:</b>",
            reference_lines,
            "",
            "<i>Posted by AI News Agent</i>",
        ]
    )

    return "\n".join(parts).strip()


def format_error_message(title: str, details: str) -> str:
    """Build a Telegram HTML error notification."""
    safe_details = _truncate_error_details(_escape_html(_sanitize_error_text(details)))
    message = "\n".join(
        [
            "🚨 <b>AI News Agent Error</b>",
            "",
            f"<b>Where:</b> {_escape_html(title)}",
            "",
            "<b>Details:</b>",
            f"<pre>{safe_details}</pre>",
            "",
            "<i>GitHub Actions marked this run as failed.</i>",
        ]
    )
    return _truncate_message(message)


def _validate_telegram_settings(token: str, chat_id: str) -> None:
    if not token:
        raise TelegramSendError("TELEGRAM_BOT_TOKEN is missing")
    if not chat_id:
        raise TelegramSendError("TELEGRAM_CHAT_ID is missing")
    if ":" not in token:
        raise TelegramSendError("TELEGRAM_BOT_TOKEN looks invalid; expected a BotFather token containing ':'")
    if not (chat_id.startswith("@") or chat_id.lstrip("-").isdigit()):
        raise TelegramSendError("TELEGRAM_CHAT_ID looks invalid; expected a numeric ID or @channelusername")


def _response_json(response: requests.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _telegram_error_message(response: requests.Response, body: dict[str, Any]) -> str:
    description = body.get("description")
    error_code = body.get("error_code", response.status_code)
    if description:
        return f"Telegram API error {error_code}: {_sanitize_error_text(description)}"

    response_text = _sanitize_error_text(getattr(response, "text", "") or response.reason)
    return f"Telegram API error {response.status_code}: {response_text}"


def _should_retry_plain_text(error: TelegramSendError | None) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "can't parse entities",
            "can't find end of the entity",
            "unsupported start tag",
            "entity",
            "parse",
        )
    )


def _escape_html(value: object) -> str:
    return html.escape(str(value).strip(), quote=False)


def _html_to_plain_text(value: str) -> str:
    text = re.sub(r"</(b|i|pre)>", "", value)
    text = re.sub(r"<(b|i|pre)>", "", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    return html.unescape(text)


def _sanitize_error_text(value: object) -> str:
    token = TELEGRAM_BOT_TOKEN
    text = str(value)
    if token:
        text = text.replace(token, "<redacted-token>")
    text = re.sub(r"/bot[^/\s]+/", "/bot<redacted-token>/", text)
    text = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot<redacted-token>", text)
    return text


def _truncate_message(message: str) -> str:
    if len(message) <= MAX_TELEGRAM_MESSAGE_LENGTH:
        return message
    suffix = "\n\n... truncated"
    return message[: MAX_TELEGRAM_MESSAGE_LENGTH - len(suffix)] + suffix


def _truncate_error_details(details: str) -> str:
    max_details_length = 3200
    if len(details) <= max_details_length:
        return details
    return details[:max_details_length] + "\n... truncated"
