from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent import fetcher


def _rss_entry(hours_old: int = 1) -> dict:
    published = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    return {
        "title": "OpenAI startup ships new AI agent model",
        "link": "https://example.com/story",
        "summary": "A new AI agent model for machine learning teams.",
        "published_parsed": published.timetuple(),
    }


def _newsapi_response(hours_old: int = 1) -> Mock:
    published = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "articles": [
            {
                "title": "Nvidia chip startup launches open source model",
                "url": "https://example.com/newsapi",
                "description": "Chip and model news from a fast AI startup.",
                "publishedAt": published.isoformat().replace("+00:00", "Z"),
                "source": {"name": "Example News"},
            }
        ]
    }
    return response


@patch("agent.fetcher.requests.get")
@patch("agent.fetcher.feedparser.parse")
def test_fetch_stories_returns_list(mock_parse, mock_get):
    mock_parse.return_value = SimpleNamespace(
        bozo=False,
        feed={"title": "Example RSS"},
        entries=[_rss_entry()],
    )
    mock_get.return_value = _newsapi_response()

    stories = fetcher.fetch_stories(newsapi_key="key")

    assert isinstance(stories, list)


@patch("agent.fetcher.requests.get")
@patch("agent.fetcher.feedparser.parse")
def test_fetch_stories_required_keys(mock_parse, mock_get):
    mock_parse.return_value = SimpleNamespace(
        bozo=False,
        feed={"title": "Example RSS"},
        entries=[_rss_entry()],
    )
    mock_get.return_value = _newsapi_response()

    stories = fetcher.fetch_stories(newsapi_key="key")

    assert stories
    for story in stories:
        assert {"title", "url", "source", "published_at"}.issubset(story.keys())


@patch("agent.fetcher.requests.get")
@patch("agent.fetcher.feedparser.parse")
def test_stories_older_than_24_hours_are_filtered_out(mock_parse, mock_get):
    mock_parse.return_value = SimpleNamespace(
        bozo=False,
        feed={"title": "Example RSS"},
        entries=[_rss_entry(hours_old=30)],
    )
    mock_get.return_value = _newsapi_response(hours_old=30)

    stories = fetcher.fetch_stories(newsapi_key="key")

    assert stories == []

