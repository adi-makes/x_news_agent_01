from __future__ import annotations

from unittest.mock import Mock, patch

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
    response.raise_for_status.return_value = None
    response.json.return_value = {"ok": True}
    mock_post.return_value = response

    sender.send_to_telegram(_post_dict(), bot_token="token", chat_id="123")

    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == "https://api.telegram.org/bottoken/sendMessage"


@patch("agent.sender.requests.post")
def test_message_is_formatted_correctly(mock_post):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"ok": True}
    mock_post.return_value = response

    sender.send_to_telegram(_post_dict(), bot_token="token", chat_id="123")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["parse_mode"] == "Markdown"
    assert "🗞 *AI & Tech Daily*" in payload["text"]
    assert "AI funding is sobering up" in payload["text"]
    assert "🔗 *Share this:* https://example.com/story" in payload["text"]
    assert "• https://example.com/story" in payload["text"]
    assert "_Posted by AI News Agent_" in payload["text"]
