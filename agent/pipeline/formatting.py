"""Formatting utilities for pipeline outputs with agent support."""

from typing import List
from textwrap import dedent

from agents import Agent, Runner

from shared.llm import AGENT_MODEL
from .models import PipelineOutput, TelegramSummary
from shared.logging import get_logger

logger = get_logger(__name__)


_FORMATTER = Agent(
    name="Telegram Formatter",
    model=AGENT_MODEL,
    instructions=dedent(
        """
        Format a set of analyzed papers into short Telegram HTML. Keep it compact.
        Output JSON with a single field `html` containing the final HTML.
        """
    ),
    output_type=TelegramSummary,
)


def _fallback_format(output: PipelineOutput) -> str:
    """Local compact HTML formatter used when the agent is not available.

    :param output: Full pipeline output to format.
    :returns: Telegram-friendly HTML string.
    """
    logger.debug(
        f"Fallback formatting: items={len(output.analyzed)} queries={len(output.generated_queries)}"
    )
    lines: List[str] = []
    lines.append("<b>Research pipeline results</b>\n")
    lines.append(f"<b>Task:</b> {output.task.query}\n")
    if output.generated_queries:
        lines.append(
            "<b>Queries:</b> " + ", ".join(output.generated_queries[:5]) + "\n\n"
        )
    for res in output.analyzed[:10]:
        title = res.candidate.title
        link = res.candidate.abs_url or res.candidate.pdf_url or ""
        lines.append(f"📄 <b>{title}</b>")
        lines.append(f"Relevance: {res.relevance:.1f}%")
        if res.summary:
            lines.append(res.summary.strip())
        if link:
            lines.append(f'🔗 <a href="{link}">Link</a>')
        lines.append("")
    return "\n".join(lines).strip()


async def to_telegram_html_agent(output: PipelineOutput) -> str:
    """Agent-based formatter; falls back to local template on failure.

    :param output: Full pipeline output to format.
    :returns: Telegram-friendly HTML string.
    """
    try:
        logger = get_logger(__name__)
        # Prepare compact JSON-like context to keep tokens low
        items = []
        for res in output.analyzed[:10]:
            items.append(
                {
                    "title": res.candidate.title,
                    "url": res.candidate.abs_url or res.candidate.pdf_url or "",
                    "relevance": res.relevance,
                    "summary": res.summary,
                }
            )
        import json

        prompt = json.dumps(
            {
                "task": output.task.query,
                "queries": output.generated_queries[:5],
                "items": items,
            }
        )
        logger.debug("Calling formatter agent")
        run_result = await Runner.run(_FORMATTER, prompt)
        out = getattr(run_result, "parsed", None)
        if out and out.html:
            logger.info("Formatter agent produced HTML output")
            return out.html
    except Exception:
        pass
    return _fallback_format(output)


def to_telegram_html(output: PipelineOutput) -> str:
    """Synchronous facade using the fallback to avoid event loop requirements.

    :param output: Full pipeline output to format.
    :returns: Telegram-friendly HTML string.
    """
    return _fallback_format(output)
