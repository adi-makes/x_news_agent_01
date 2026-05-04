from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from agent import generator


def _story() -> dict:
    return {
        "title": "OpenAI launches practical AI agent model",
        "url": "https://example.com/openai-agent",
        "source": "Example",
        "published_at": "2026-05-04T00:00:00+00:00",
        "summary": "A new model for AI agent workflows.",
    }


def _groq_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _valid_payload(post: str = "AI agents are getting less flashy and more useful. Good.") -> str:
    return json.dumps(
        {
            "post": post,
            "replies": [],
            "share_link": "https://example.com/openai-agent",
            "references": ["https://example.com/openai-agent", "https://example.com/ref"],
            "story_title": "OpenAI launches practical AI agent model",
        }
    )


@patch("agent.generator.Groq")
def test_generate_post_returns_required_keys(mock_groq):
    mock_client = mock_groq.return_value
    mock_client.chat.completions.create.return_value = _groq_response(_valid_payload())

    post = generator.generate_post([_story()], groq_api_key="key")

    assert {"post", "replies", "share_link", "references", "story_title"}.issubset(post.keys())
    assert mock_client.chat.completions.create.call_args.kwargs["model"] == "llama-3.3-70b-versatile"
    assert mock_client.chat.completions.create.call_args.kwargs["response_format"] == {
        "type": "json_object"
    }


@patch("agent.generator.Groq")
def test_post_text_is_under_280_chars(mock_groq):
    mock_client = mock_groq.return_value
    mock_client.chat.completions.create.return_value = _groq_response(_valid_payload())

    post = generator.generate_post([_story()], groq_api_key="key")

    assert len(post["post"]) <= 280


@patch("agent.generator.Groq")
def test_json_parse_failure_triggers_retry(mock_groq):
    mock_client = mock_groq.return_value
    mock_client.chat.completions.create.side_effect = [
        _groq_response("not json"),
        _groq_response(_valid_payload("Retry made this clean JSON.")),
    ]

    post = generator.generate_post([_story()], groq_api_key="key")

    assert post["post"] == "Retry made this clean JSON."
    assert mock_client.chat.completions.create.call_count == 2


@patch("agent.generator.Groq")
def test_markdown_wrapped_python_style_json_parses(mock_groq):
    mock_client = mock_groq.return_value
    mock_client.chat.completions.create.return_value = _groq_response(
        """```json
        {
          'post': "OpenAI's agent push is getting practical.",
          'replies': [],
          'share_link': 'https://example.com/openai-agent',
          'references': ['https://example.com/openai-agent'],
          'story_title': 'OpenAI launches practical AI agent model'
        }
        ```"""
    )

    post = generator.generate_post([_story()], groq_api_key="key")

    assert post["post"] == "OpenAI's agent push is getting practical."


@patch("agent.generator.Groq")
def test_share_link_falls_back_to_fetched_story_url(mock_groq):
    mock_client = mock_groq.return_value
    mock_client.chat.completions.create.return_value = _groq_response(
        json.dumps(
            {
                "post": "Useful AI news.",
                "replies": [],
                "share_link": "https://unrelated.example.com",
                "references": [],
                "story_title": "OpenAI launches practical AI agent model",
            }
        )
    )

    post = generator.generate_post([_story()], groq_api_key="key")

    assert post["share_link"] == "https://example.com/openai-agent"
    assert post["references"][0] == "https://example.com/openai-agent"
