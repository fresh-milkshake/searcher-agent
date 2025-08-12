---
title: Contributing
---

# Contributing

## Guidelines

- Use `uv` for all package operations.
- Follow PEP 8, add type hints and docstrings.
- Keep functions small and focused.
- Prefer early returns and descriptive names.
- Project language is English; user-facing bot messages may be localized.

## Project conventions

- Python 3.13, static types, Pydantic models in pipeline
- Logging via Loguru; logs in `logs/`
- Database layer: async SQLAlchemy in `shared/database.py` (new), legacy Peewee in `shared/db.py` kept for backward compatibility
- Bot: aiogram v3, Telegram HTML render
- REST API: FastAPI in `api/app.py`

## Dev setup

```bash
uv sync --group dev
```

## Quality checks

Run targeted quality checks:

```bash
uv run python quality-check.py <target>
```

Run tests:

```bash
uv run pytest
```

## Documentation

- Author: fresh-milkshake (`https://github.com/fresh-milkshake`)
- Build: `uv run sphinx-build -b html docs docs/_build/html`

### Adding or updating docs

- Keep pages concise and practical; prefer task-oriented examples.
- Update `README.md` and `docs/` together to avoid drift.
- Regenerate API docs if signatures change.


