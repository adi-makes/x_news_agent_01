"""Generate Twitter/X-style posts with Groq."""

from __future__ import annotations

import json
import logging
import ast
from typing import Any

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL


logger = logging.getLogger(__name__)
MODEL = GROQ_MODEL
SYSTEM_PROMPT = (
    "You are a professional tech creator on X (Twitter) with 500k followers.\n"
    "You write posts that are sharp, credible, and genuinely useful to developers,\n"
    "founders, and AI enthusiasts. Your tone is confident, direct, and human — \n"
    "never corporate, never hype-driven.\n\n"
    "Rules you never break:\n"
    "- Open with a hook that states WHY this matters, not just WHAT it is.\n"
    "- Every post must deliver one clear insight or takeaway.\n"
    "- Use hashtags ONLY if they are widely followed and contextually relevant "
    "(e.g. #AI, #OpenSource). Max 2 hashtags across the entire thread.\n"
    "- Never use phrases like 'game-changer', 'revolutionary', 'groundbreaking'.\n"
    "- No excessive emojis. Max 1 emoji per post part, only if it adds clarity.\n"
    "- Each part must be self-contained enough that it makes sense if seen alone.\n"
    "- Always factual. Never speculate without signaling it (e.g. 'could mean...').\n"
    "- If splitting into a thread, each part must carry new information — \n"
    "  never waste a tweet on just links.\n"
)


def generate_post(stories: list[dict], groq_api_key: str | None = None) -> dict:
    """Generate and parse a post dictionary from the Groq API."""
    if not stories:
        raise ValueError("generate_post requires at least one story")

    client = Groq(api_key=groq_api_key or GROQ_API_KEY)
    formatted_stories = _format_stories(stories)
    prompt = _build_prompt(formatted_stories)

    content = _call_groq(client, prompt)
    try:
        return _validate_post(_parse_json_response(content), stories)
    except (json.JSONDecodeError, SyntaxError, ValueError, TypeError):
        logger.exception("Failed to parse or validate Groq response; retrying once")

    retry_prompt = (
        "Return only valid JSON with keys post, replies, share_link, references, story_title. "
        "No markdown. Use this story list:\n"
        f"{formatted_stories}"
    )
    content = _call_groq(client, retry_prompt)
    return _validate_post(_parse_json_response(content), stories)


def _call_groq(client: Groq, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=800,
        response_format={"type": "json_object"},
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
        "Pick the most technically interesting story and write an X (Twitter) post.\n\n"
        "STRUCTURE RULES:\n"
        "- If the post fits in 280 characters: return a single punchy post.\n"
        "- If it needs more space: split into a thread (max 3 parts, each ≤280 chars).\n"
        "  Label them (1/3), (2/3), (3/3) etc.\n"
        "- EVERY part must contain substance — no part should exist only to share links.\n"
        "  Weave the share link naturally into a part that has real content.\n\n"
        "CONTENT RULES:\n"
        "- Part 1 must open with a hook: a surprising fact, a bold claim with "
        "evidence, or a sharp 'why this matters' framing.\n"
        "- Explain what the tool/story actually does in plain terms.\n"
        "- Add context: who built it, what problem it solves, what makes it "
        "technically notable.\n"
        "- Only add hashtags if they are high-signal and relevant (e.g. #AI, "
        "#OpenSource). Max 2 across the full thread.\n"
        "- End the thread with a forward-looking thought or clear call to action.\n\n"
        "Return ONLY valid JSON in this exact format:\n"
        "{\n"
        "  \"post\": \"main post text (1/N if thread)\",\n"
        "  \"replies\": [\"part 2 text\", \"part 3 text\"],\n"
        "  \"share_link\": \"https://...\",\n"
        "  \"references\": [\"https://...\", \"https://...\"],\n"
        "  \"story_title\": \"original headline\"\n"
        "}"
    )


def _parse_json_response(content: str) -> dict:
    cleaned = _extract_json_object(_strip_markdown_fence(content))
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Groq response JSON must be an object")
        return parsed


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


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return content
    return content[start : end + 1]


def _validate_post(post: dict[str, Any], stories: list[dict] | None = None) -> dict:
    required = ["post", "replies", "share_link", "references", "story_title"]
    missing = [key for key in required if key not in post]
    if missing:
        raise ValueError(f"Generated post missing required keys: {', '.join(missing)}")

    stories = stories or []
    story_urls = {str(story.get("url", "")).strip() for story in stories if story.get("url")}
    fallback_story = stories[0] if stories else {}

    post["post"] = str(post["post"]).strip()
    post["replies"] = [str(reply).strip() for reply in post["replies"]] if isinstance(post["replies"], list) else []
    post["references"] = [str(ref).strip() for ref in post["references"]] if isinstance(post["references"], list) else []
    post["share_link"] = str(post["share_link"]).strip()
    post["story_title"] = str(post["story_title"]).strip()

    if story_urls and post["share_link"] not in story_urls:
        logger.warning("Generated share_link was not a fetched story URL; using top story URL")
        post["share_link"] = str(fallback_story.get("url", "")).strip()

    if not post["story_title"] and fallback_story:
        post["story_title"] = str(fallback_story.get("title", "")).strip()

    references = [ref for ref in post["references"] if ref]
    if post["share_link"] and post["share_link"] not in references:
        references.insert(0, post["share_link"])
    post["references"] = list(dict.fromkeys(references))[:3]

    for part in [post["post"], *post["replies"]]:
        if len(part) > 280:
            raise ValueError("Generated post part exceeds 280 characters")

    return post
