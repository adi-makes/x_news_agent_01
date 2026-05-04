"""Central configuration for the AI News Agent."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
SEEN_STORIES_PATH = DATA_DIR / "seen_stories.json"

load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

REQUIRED_ENV_VARS = {
    "GROQ_API_KEY": GROQ_API_KEY,
    "NEWSAPI_KEY": NEWSAPI_KEY,
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
}


def validate_config() -> None:
    """Raise a clear error if any required environment variable is missing."""
    missing = [name for name, value in REQUIRED_ENV_VARS.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Set them in .env locally or GitHub Actions secrets in CI."
        )

