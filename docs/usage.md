---
title: Usage
---

# Usage

## CLI entrypoints

- `start_bot.py`: launches the Telegram bot.
- `start_agent.py`: starts the agent service.

### Environment

- `TELEGRAM_BOT_TOKEN`: required for bot; in docs build it's set to a dummy.

### Development profiles

- `AGENT_DRY_RUN=1`: do not persist results, only send summaries.

## Code structure

- `agent/`: agent pipeline, browsing tools, and orchestration.
- `bot/`: Telegram bot handlers, dispatcher, and utils.
- `shared/`: shared utilities like database, logging, LLM wrappers, and events.

## Telegram bot commands

Core commands (subset):

- `/start`: intro and help
- `/task "Title" description`: create a new autonomous search task
- `/status_task`: list your tasks
- `/pause_task <id>`, `/resume_task <id>`: control a task
- `/settings`: view current settings
- `/set_relevance relevance <0-100>`: set minimum relevance threshold
- `/set_notification [instant|daily|weekly] <0-100>`: configure notifications
- `/set_group` and `/unset_group`: switch notifications to a group chat

Quick links:

- Manage your bot with [@BotFather](https://t.me/BotFather)
- aiogram message formatting: [HTML mode](https://core.telegram.org/bots/api#formatting-options)
- Group chat setup: add your bot to a group, then run `/set_group`

## Configuration reference

- `DATABASE_PATH`: SQLite file path; defaults to `database.db`
- `AGENT_POLL_SECONDS`: seconds between agent iterations; default `30`
- `AGENT_ID`: identifier for the agent; default `main_agent`
- `PIPELINE_USE_AGENTS_ANALYZE`: `1` to enable LLM analysis; default off

## Typical workflow

1. Start bot and agent
2. Create a task with `/task` and your goal
3. The agent generates queries, collects papers, ranks, analyzes, and decides
4. You receive concise summaries in Telegram when useful items appear

## Development

- Run tests with `uv run pytest`.
- Lint and type-check via `ruff` and `pyright`.

### Local docs preview

```bash
uv run sphinx-build -b html docs docs/_build/html
start docs/_build/html/index.html
```



