---
title: Contributing
---

# Contributing

## Guidelines

- Use `uv` for all package operations.
- Follow PEP 8, add type hints and docstrings.
- Keep functions small and focused.
- Prefer early returns and descriptive names.

## Project conventions

- Python 3.13, static types, Pydantic models in pipeline
- Logging via Loguru; logs in `logs/`
- Database layer: async SQLAlchemy in `shared/db.py`
- Bot: aiogram v3, Telegram HTML render

## Dev setup

```bash
uv sync --group dev
```

## Quality checks

Run targeted quality checks:

```bash
uv run python quality-check.py <target>
```

## Documentation

- Author: fresh-milkshake (`https://github.com/fresh-milkshake`)
- Build: `uv run sphinx-build -b html docs docs/_build/html`


