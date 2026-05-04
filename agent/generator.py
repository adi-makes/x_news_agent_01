"""Generate Twitter/X-style posts with Groq."""

from __future__ import annotations

import json
import logging
from typing import Any

from groq import Groq

from config import GROQ_API_KEY


logger = logging.getLogger(__name__)
MODEL = "llama3-70b-8192"
SYSTEM_PROMPT = (
    "You are a sharp, insightful tech Twitter account with 500k followers.\n"
    "You write punchy, clear posts that cut through hype. No cringe. No \n"
    "excessive emojis. Max 2 hashtags per post. Always factual."
)


def generate_post(stories: list[dict], groq_api_key: str | None = None) -> dict:
    """Generate and parse a post dictionary from the Groq API."""
    if not stories:
        raise ValueError("generate_post requires at least one story")

    client = Groq(api_key=groq_api_key or GROQ_API_KEY)
    formatted_stories = _format_stories(stories)
    prompt = _build_prompt(formatted_stories)

    try:
        content = _call_groq(client, prompt)
        return _validate_post(_parse_json_response(content))
    except Exception:
        logger.exception("Failed to parse Groq response; retrying once")

    retry_prompt = (
        "Return only valid JSON with keys post, replies, share_link, references, story_title. "
        "No markdown. Use this story list:\n"
        f"{formatted_stories}"
    )
    content = _call_groq(client, retry_prompt)
    return _validate_post(_parse_json_response(content))


def _call_groq(client: Groq, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""


def _format_stories(stories: list[dict]) -> str:
    formatted = []
    for index, story in enumerate(stories, start=1):
        formatted.append(
            "\n".join(
                [
                    f"{index}. {story.get('title', '')}",
                    f"Source: {story.get('source', '')}",
                    f"Published: {story.get('published_at', '')}",
                    f"URL: {story.get('url', '')}",
                    f"Summary: {story.get('summary', '')}",
                ]
            )
        )
    return "\n\n".join(formatted)


def _build_prompt(formatted_stories: str) -> str:
    return (
        "Here are today's top tech and AI news stories:\n"
        f"{formatted_stories}\n\n"
        "Write a Twitter/X post about the most interesting story.\n"
        "Rules:\n"
        "- If the post fits in 280 characters, return just the post.\n"
        "- If it needs more space, split into post, reply1, reply2 (max 3 parts, \n"
        "  each under 280 chars). Number them if split: (1/2), (2/2) etc.\n"
        "- Include the story URL as the share link.\n"
        "- Add 2-3 reference links for fact-checking (can be the source + 1-2 related).\n"
        "- Max 2 hashtags total across all parts.\n"
        "- Tone: confident, direct, a little witty. Not cringe.\n\n"
        "Return ONLY valid JSON in this exact format:\n"
        "{\n"
        "  'post': 'main post text here',\n"
        "  'replies': ['reply1 text', 'reply2 text'],\n"
        "  'share_link': 'https://...',\n"
        "  'references': ['https://...', 'https://...'],\n"
        "  'story_title': 'original headline'\n"
        "}"
    )


def _parse_json_response(content: str) -> dict:
    cleaned = _strip_markdown_fence(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        normalized = cleaned.replace("'", '"')
        return json.loads(normalized)


def _strip_markdown_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _validate_post(post: dict[str, Any]) -> dict:
    required = ["post", "replies", "share_link", "references", "story_title"]
    missing = [key for key in required if key not in post]
    if missing:
        raise ValueError(f"Generated post missing required keys: {', '.join(missing)}")

    post["post"] = str(post["post"]).strip()
    post["replies"] = post["replies"] if isinstance(post["replies"], list) else []
    post["references"] = post["references"] if isinstance(post["references"], list) else []
    post["share_link"] = str(post["share_link"]).strip()
    post["story_title"] = str(post["story_title"]).strip()

    for part in [post["post"], *post["replies"]]:
        if len(part) > 280:
            raise ValueError("Generated post part exceeds 280 characters")

    return post

