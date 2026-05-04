# AI News Agent

## What this is

AI News Agent is a Python 3.11 bot that fetches trending tech and AI news, generates a concise Twitter/X-style post with Groq, and sends it to Telegram. It runs every day at 8:00 AM IST with GitHub Actions and commits `seen_stories.json` back to the repo so it does not post duplicate stories.

## Prerequisites

- A free [Groq](https://console.groq.com/) account for the Llama 3 API key.
- A free [NewsAPI](https://newsapi.org/) account for news search.
- A free Telegram account and bot created through [@BotFather](https://t.me/BotFather).
- A GitHub repository with Actions enabled.

## Setup

1. Clone the repo:

   ```bash
   git clone <your-repo-url>
   cd <your-repo-name>
   ```

2. Copy `.env.example` to `.env` and fill in the values:

   ```bash
   cp .env.example .env
   ```

   `GROQ_MODEL` defaults to `llama-3.3-70b-versatile`, Groq's recommended replacement for the retired `llama3-70b-8192` model.

3. Get a Groq API key by signing in at [console.groq.com](https://console.groq.com/), opening API Keys, and creating a new key.

4. Get a NewsAPI key by signing up at [newsapi.org](https://newsapi.org/) and copying your free developer API key.

5. Create a Telegram bot by opening Telegram, talking to [@BotFather](https://t.me/BotFather), sending `/newbot`, and copying the bot token it gives you.

6. Get your Telegram chat ID by talking to [@userinfobot](https://t.me/userinfobot). For a channel, add your bot to the channel and use the channel ID or username.

7. Add secrets to your GitHub repo at `Settings > Secrets > Actions > New secret`. Add `GROQ_API_KEY`, `NEWSAPI_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`.

8. Enable GitHub Actions write permissions at `Settings > Actions > General > Workflow permissions > Read and write permissions`. This lets the workflow commit updates to `data/seen_stories.json`.

9. Install dependencies locally:

   ```bash
   pip install -r requirements.txt
   ```

## How to test locally

Run the agent from the repo root:

```bash
python main.py
```

You can also run the test suite:

```bash
pytest
```

## How to trigger manually

Open your GitHub repository, go to `Actions`, choose the `AI News Agent` workflow, and click the `Run workflow` button.

## Error notifications

If the agent fails during a run, it logs the full traceback, sends a concise error notification to the configured Telegram chat, and exits with code `1` so GitHub Actions marks the run as failed. If Telegram itself is unavailable or misconfigured, the failure is still logged and the workflow still fails.

For Telegram `Bad Request: chat not found`, check that `TELEGRAM_CHAT_ID` is a numeric user ID, a group/channel ID such as `-100...`, or a public `@channelusername`. Also make sure you have started the bot in Telegram, or added the bot to the target group/channel with permission to post.

## Folder structure explanation

- `.github/workflows/news_agent.yml` runs the daily GitHub Actions job and commits deduplication state.
- `agent/fetcher.py` fetches RSS and NewsAPI stories, filters them by freshness and keywords, deduplicates by URL, and ranks the top five.
- `agent/generator.py` calls Groq with `llama3-70b-8192` and parses the JSON post response.
- `agent/sender.py` formats and sends the Telegram message.
- `agent/dedup.py` reads and writes `data/seen_stories.json`.
- `data/seen_stories.json` stores URLs that were already sent.
- `tests/` contains mocked unit tests for fetching, generation, and Telegram delivery.
- `config.py` loads `.env` locally and reads GitHub Actions secrets in CI.
- `main.py` orchestrates the full pipeline.

## How to customize topics / tone

To customize topics, edit `KEYWORDS`, `RSS_FEEDS`, or `NEWSAPI_QUERY` in `agent/fetcher.py`. To customize writing style, edit `SYSTEM_PROMPT` or the user prompt template in `agent/generator.py`. To change Groq models without editing code, set `GROQ_MODEL` in `.env` or your GitHub Actions environment.
