---
title: searcher-agent Documentation
---

# searcher-agent

Welcome to the documentation for the `searcher-agent` project.

This site contains an overview, how to get started, usage examples, and a full
API reference generated from the source code in `agent/`, `bot/`, and `shared/`.

:::{toctree}
:maxdepth: 2
:caption: Contents

getting-started
usage
use-cases
contributing
api/modules
:::

## Project overview

`searcher-agent` provides an end-to-end research assistant that:

- Generates multiple search queries for a user task
- Retrieves arXiv candidates and deduplicates them
- Ranks with BM25 over title + abstract
- Analyzes the top candidates (LLM-backed or heuristic)
- Decides whether to notify and formats a concise report for Telegram

You can interact via Telegram, or call the REST API to run the pipeline
programmatically. See the pages above to learn how to install, run, and extend
the project.


