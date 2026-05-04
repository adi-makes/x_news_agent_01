from __future__ import annotations

from unittest.mock import Mock, patch

import requests

from agent import sender


def _post_dict() -> dict:
    return {
        "post": "AI funding is sobering up. Useful beats splashy.",
        "replies": ["That is probably healthy for builders."],
        "share_link": "https://example.com/story",
        "references": ["https://example.com/story", "https://example.com/ref"],
        "story_title": "AI startup story",
    }


@patch("agent.sender.requests.post")
def test_send_to_telegram_calls_correct_endpoint(mock_post):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"ok": True}
    mock_post.return_value = response

    sender.send_to_telegram(_post_dict(), bot_token="123:token", chat_id="123")

    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == "https://api.telegram.org/bot123:token/sendMessage"


@patch("agent.sender.requests.post")
def test_message_is_formatted_correctly(mock_post):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"ok": True}
    mock_post.return_value = response

    sender.send_to_telegram(_post_dict(), bot_token="123:token", chat_id="123")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["parse_mode"] == "HTML"
    assert "🗞 <b>AI &amp; Tech Daily</b>" in payload["text"]
    assert "AI funding is sobering up" in payload["text"]
    assert "🔗 <b>Share this:</b> https://example.com/story" in payload["text"]
    assert "• https://example.com/story" in payload["text"]
    assert "<i>Posted by AI News Agent</i>" in payload["text"]


def test_html_dynamic_text_is_escaped():
    message = sender.format_telegram_message(
        {
            "post": "OpenAI <model> & ships",
            "replies": [],
            "share_link": "https://example.com/a?x=1&y=2",
            "references": ["https://example.com/a?x=1&y=2"],
        }
    )

    assert "OpenAI &lt;model&gt; &amp; ships" in message
    assert "https://example.com/a?x=1&amp;y=2" in message


@patch("agent.sender.requests.post")
def test_send_to_telegram_raises_on_request_error(mock_post):
    mock_post.side_effect = requests.ConnectionError("network down")

    try:
        sender.send_to_telegram(_post_dict(), bot_token="123:token", chat_id="123")
    except sender.TelegramSendError as exc:
        assert "Telegram HTTP request failed" in str(exc)
    else:
        raise AssertionError("Expected TelegramSendError")


@patch("agent.sender.requests.post")
def test_send_error_to_telegram_returns_false_on_failure(mock_post):
    mock_post.side_effect = requests.ConnectionError("network down")

    assert sender.send_error_to_telegram("ValueError", "traceback", bot_token="123:token", chat_id="123") is False


def test_error_message_is_truncated():
    message = sender.format_error_message("Failure", "x" * 5000)

    assert len(message) <= sender.MAX_TELEGRAM_MESSAGE_LENGTH
    assert "truncated" in message


@patch("agent.sender.requests.post")
def test_telegram_api_error_uses_description_without_token(mock_post):
    response = Mock()
    response.status_code = 400
    response.reason = "Bad Request"
    response.text = '{"ok":false}'
    response.json.return_value = {
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: chat not found",
    }
    mock_post.return_value = response

    try:
        sender.send_to_telegram(_post_dict(), bot_token="123:SECRET", chat_id="123")
    except sender.TelegramSendError as exc:
        assert str(exc) == "Telegram API error 400: Bad Request: chat not found"
        assert "SECRET" not in str(exc)
    else:
        raise AssertionError("Expected TelegramSendError")


@patch("agent.sender.requests.post")
def test_formatted_message_retries_as_plain_text(mock_post):
    first = Mock()
    first.status_code = 400
    first.reason = "Bad Request"
    first.text = ""
    first.json.return_value = {
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: can't parse entities",
    }
    second = Mock()
    second.status_code = 200
    second.json.return_value = {"ok": True}
    mock_post.side_effect = [first, second]

    sender.send_to_telegram(_post_dict(), bot_token="123:SECRET", chat_id="123")

    assert mock_post.call_count == 2
    retry_payload = mock_post.call_args.kwargs["json"]
    assert "parse_mode" not in retry_payload
    assert "AI & Tech Daily" in retry_payload["text"]
