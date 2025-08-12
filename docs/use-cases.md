---
title: Use Cases
---

# Use Cases

## Research assistants

You can use the system to keep an eye on new papers from arXiv by choosing specific categories or keywords. The assistant will automatically sort the results, summarize the most relevant ones, and send you updates on Telegram. 

For example, if you are interested in foundation models for medical imaging, you can set up a weekly summary that only includes papers with at least 50% relevance. Each week, you’ll get a short list of 3 to 5 key papers, each with a link to arXiv.

## Teams and communities

Groups can create shared watchlists and get regular, easy-to-read updates. The system helps everyone keep track of what’s important by using simple relevance thresholds.

For example, you can make a group chat, add the bot with the `/set_group` command, and let everyone in your team or community share topics. This way, educators or researchers can stay informed together.

## Product and engineering

If you work in product or engineering, you can use the assistant to look for new algorithms, benchmarks, or libraries. It will collect summaries and important details so you can quickly decide what’s worth a closer look.

For example, you might want to follow topics like “OCR for receipts” or “diffusion for texture generation.” The assistant will send you useful notes and links to help you investigate new developments.

## Education

The system can help students and teachers by creating simple summaries of complex topics and putting together reading lists with the latest research.

For example, students can get easy-to-understand explanations with links to the original papers. This is especially helpful for weekly reading assignments or study groups.

## REST API automations

Use the REST API to integrate the pipeline into internal tools or scheduled jobs:

```bash
curl -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI for medical imaging",
    "categories": ["cs.CV"],
    "max_queries": 5,
    "bm25_top_k": 20,
    "max_analyze": 10,
    "min_relevance": 50.0
  }'
```

