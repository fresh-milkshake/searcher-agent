---
title: Getting Started
---

# Getting Started

## Installation

The project uses `uv` for dependency management. Create and sync the
environment:

```bash
uv sync
```

### Prerequisites

- Python 3.13 — get it from [python.org downloads](https://www.python.org/downloads/)
- A Telegram Bot token — create a bot via [BotFather](https://t.me/BotFather)
- LLM API keys: [OpenAI API key](https://platform.openai.com/api-keys),
  [OpenRouter key](https://openrouter.ai/keys)

### Install uv for Python dependencies

- Follow [uv install docs](https://docs.astral.sh/uv/getting-started/installation/)
- But if you want to install uv here and now:

```bash
pip install uv
```

### Create a Telegram bot (token)

1. Open [BotFather](https://t.me/BotFather) in Telegram
2. Send `/newbot` and follow prompts to name your bot
3. Copy the provided token and add it to your `.env` as `TELEGRAM_BOT_TOKEN`

## Configure environment

Create a `.env` file in the project root:

```bash
copy .env.example .env
```

Example `.env` content:

```ini
# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# Database
DATABASE_PATH=database.db

# Agent runtime
AGENT_POLL_SECONDS=30
AGENT_DRY_RUN=0
AGENT_ID=main_agent

# LLM backends
# If you dont want to use OpenAI, then leave it like "OPENAI_API_KEY="
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...

# Pipeline toggles
PIPELINE_USE_AGENTS_ANALYZE=1
```

## Initialize the database

No extra steps are required on first run; the SQLite database and tables will
be created automatically. Existing deployments can set `DATABASE_PATH` to a
custom location.

## Building the documentation

```bash
uv run sphinx-build -b html docs docs/_build/html
```

Open `docs/_build/html/index.html` in a browser to view the site.

## Running the project

Run the Telegram bot and agent entrypoints:

```bash
uv run python start_bot.py
uv run python start_agent.py
```

### Quickstart checklist

1. Create `.env` with `TELEGRAM_BOT_TOKEN`
2. `uv sync`
3. Start the bot and the agent (two terminals)
4. Open Telegram and send `/start` to your bot
5. Create a task, e.g. `/task "AI for medical imaging" Find practical studies`

## Troubleshooting

- If the bot exits with “TELEGRAM_BOT_TOKEN not found”, populate `.env`.
- If you see rate limits or model errors, set API keys and retry.
- Logs are written to `logs/YYYY-MM-DD.log`.

## Helpful links

- uv docs: [docs.astral.sh/uv](https://docs.astral.sh/uv/)
- aiogram docs: [docs.aiogram.dev](https://docs.aiogram.dev/)
- Sphinx docs: [sphinx-doc.org](https://www.sphinx-doc.org/)
- Telegram bots FAQ: [telegram.org/faq#bots](https://telegram.org/faq#bots)
- Project author: [fresh-milkshake](https://github.com/fresh-milkshake)

See also: [Usage](usage), [For everyone](for-everyone), [Use cases](use-cases).


