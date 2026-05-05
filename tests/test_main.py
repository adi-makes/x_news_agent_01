from __future__ import annotations

from unittest.mock import Mock

import main


def _story() -> dict:
    return {
        "title": "OpenAI launches practical AI agent model",
        "url": "https://example.com/openai-agent",
        "source": "Example",
        "published_at": "2026-05-04T00:00:00+00:00",
        "summary": "",
    }


def _post() -> dict:
    return {
        "post": "Useful AI news.",
        "replies": [],
        "share_link": "https://example.com/openai-agent",
        "references": ["https://example.com/openai-agent"],
        "story_title": "OpenAI launches practical AI agent model",
    }


def test_main_notifies_telegram_on_unhandled_error(monkeypatch):
    notify = Mock(return_value=True)
    monkeypatch.setattr(main, "validate_config", Mock())
    monkeypatch.setattr(main.fetcher, "fetch_stories", Mock(side_effect=RuntimeError("fetch exploded")))
    monkeypatch.setattr(main.sender, "send_error_to_telegram", notify)

    assert main.main() == 1

    notify.assert_called_once()
    assert notify.call_args.args[0] == "RuntimeError"
    assert "fetch exploded" in notify.call_args.args[1]


def test_main_happy_path_marks_sent_after_send(monkeypatch):
    monkeypatch.setattr(main, "validate_config", Mock())
    monkeypatch.setattr(main.fetcher, "fetch_stories", Mock(return_value=[_story()]))
    monkeypatch.setattr(main.dedup, "filter_seen", Mock(return_value=[_story()]))
    monkeypatch.setattr(main.generator, "generate_post", Mock(return_value=_post()))
    send = Mock()
    mark_sent = Mock()
    monkeypatch.setattr(main.sender, "send_to_telegram", send)
    monkeypatch.setattr(main.dedup, "mark_sent", mark_sent)

    assert main.main() == 0

    send.assert_called_once_with(_post())
    mark_sent.assert_called_once_with("https://example.com/openai-agent")


def test_main_sends_status_when_no_stories(monkeypatch):
    status = Mock()
    monkeypatch.setattr(main, "validate_config", Mock())
    monkeypatch.setattr(main.fetcher, "fetch_stories", Mock(return_value=[]))
    monkeypatch.setattr(main.sender, "send_status_to_telegram", status)

    assert main.main() == 0

    status.assert_called_once()
    assert status.call_args.args[0] == "No post sent today."
    assert "No fresh AI or tech stories" in status.call_args.args[1][0]


def test_main_sends_status_when_all_stories_seen(monkeypatch):
    status = Mock()
    monkeypatch.setattr(main, "validate_config", Mock())
    monkeypatch.setattr(main.fetcher, "fetch_stories", Mock(return_value=[_story()]))
    monkeypatch.setattr(main.dedup, "filter_seen", Mock(return_value=[]))
    monkeypatch.setattr(main.sender, "send_status_to_telegram", status)

    assert main.main() == 0

    status.assert_called_once()
    assert status.call_args.args[0] == "No post sent today."
    assert "Fetched 1 candidate stories." in status.call_args.args[1]
    assert "data/seen_stories.json" in status.call_args.args[1][1]


def test_main_rejects_malformed_story(monkeypatch):
    notify = Mock(return_value=True)
    monkeypatch.setattr(main, "validate_config", Mock())
    monkeypatch.setattr(main.fetcher, "fetch_stories", Mock(return_value=[{"title": "Missing fields"}]))
    monkeypatch.setattr(main.sender, "send_error_to_telegram", notify)

    assert main.main() == 1

    assert "missing required fields" in notify.call_args.args[1]


def test_main_does_not_notify_telegram_about_telegram_failure(monkeypatch):
    notify = Mock(return_value=True)
    monkeypatch.setattr(main, "validate_config", Mock())
    monkeypatch.setattr(main.fetcher, "fetch_stories", Mock(return_value=[_story()]))
    monkeypatch.setattr(main.dedup, "filter_seen", Mock(return_value=[_story()]))
    monkeypatch.setattr(main.generator, "generate_post", Mock(return_value=_post()))
    monkeypatch.setattr(main.sender, "send_to_telegram", Mock(side_effect=main.sender.TelegramSendError("chat not found")))
    monkeypatch.setattr(main.sender, "send_error_to_telegram", notify)

    assert main.main() == 1

    notify.assert_not_called()
