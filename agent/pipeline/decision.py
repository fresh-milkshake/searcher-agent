"""Decisioning: scoring, selection, and reporting with agent support.

This module filters analyzed items, scores them with heuristics, and optionally
uses an agent to produce a plain-text report when there are strong candidates.
"""

from textwrap import dedent
from typing import List, Optional

from shared.llm import get_agent_model
from shared.logging import get_logger
from .models import AnalysisResult, DecisionReport, PipelineTask, ScoredAnalysis
from .utils import retry_async


logger = get_logger(__name__)


def score_result(task: PipelineTask, result: AnalysisResult) -> float:
    """Compute overall score in ``[0, 100]`` using relevance and simple boosts.

    :param task: The pipeline task providing thresholds.
    :param result: A single analysis result to score.
    :returns: Score in the range ``[0, 100]``.
    """

    score = float(max(0.0, min(100.0, result.relevance)))
    # Tiny boost if summary mentions code/dataset/benchmark
    text = (result.summary or "").lower()
    if any(k in text for k in ("code", "github", "dataset", "benchmark")):
        score = min(100.0, score + 5.0)
    return score


def select_top(
    task: PipelineTask, analyzed: List[AnalysisResult]
) -> List[ScoredAnalysis]:
    """Score and keep items above ``min_relevance`` in descending order.

    The output is trimmed to at most three items to keep reports concise.

    :param task: Pipeline task with ``min_relevance``.
    :param analyzed: Analysis results to select from.
    :returns: Compact, sorted selection of :class:`ScoredAnalysis`.
    """

    items: List[ScoredAnalysis] = []
    for r in analyzed:
        s = score_result(task, r)
        if s >= task.min_relevance:
            items.append(ScoredAnalysis(result=r, overall_score=s))
    items.sort(key=lambda x: x.overall_score, reverse=True)
    # Keep report concise: at most top 3
    return items[: max(1, min(len(items), 3))]


def _get_reporter():
    """Lazy initialization of the reporter agent."""
    from agents import Agent
    return Agent(
        name="Decision Reporter",
        model=get_agent_model(),
        instructions=dedent(
            """
            You are a research assistant. Given a user task and a small set of analyzed papers
            with summaries and relevance, decide whether there are truly helpful items.

            If there are, produce a plain text report focused on the user task:
            - Start with one header line: "Findings for your task: <task>"
            - Then list up to 3 items in this structure (each 1–2 lines):
              - <Title>
                Why useful for this task: <one short sentence tailored to the task>
                Link: <url>
            - Be brief and actionable: 6–12 lines total for the whole report
            - Keep language clear and human-friendly; no HTML/Markdown, plain text only

            IMPORTANT: Strictly fit within 3000 characters.
            You must return a JSON object with two fields:
            {"should_notify": boolean, "report_text": string|null}
            - If there is nothing truly helpful, set should_notify=false and report_text=null
            - Otherwise set should_notify=true and report_text to the plain text report
            """
        ),
        output_type=DecisionReport,
    )


async def make_decision_and_report(
    task: PipelineTask, selected: List[ScoredAnalysis]
) -> DecisionReport:
    """Generate a plain-text report or decide to skip notifying the user.

    Uses an LLM-based reporter when available, falling back to a local
    template otherwise.

    :param task: The source task that describes user intent.
    :param selected: A compact list of scored analyses.
    :returns: Decision and optional report text.
    """

    if not selected:
        return DecisionReport(should_notify=False, report_text=None)

    try:
        import json

        payload = json.dumps(
            {
                "task": task.query,
                "items": [
                    {
                        "title": s.result.candidate.title,
                        "summary": s.result.summary,
                        "score": s.overall_score,
                        "link": s.result.candidate.abs_url
                        or s.result.candidate.pdf_url,
                    }
                    for s in selected
                ],
            }
        )
        from agents import Runner
        result = await retry_async(lambda: Runner.run(_get_reporter(), payload))
        return result.final_output
    except Exception as error:
        logger.warning(f"Decision reporter failed, fallback to template: {error}")

    # Fallback template — concise, single-message friendly
    lines: List[str] = []
    lines.append(f"Findings for your task: {task.query}\n")
    for s in selected[:3]:
        title = s.result.candidate.title
        link = s.result.candidate.abs_url or s.result.candidate.pdf_url or ""
        why = _why_for_task(task.query, s.result.summary or "")
        lines.append(f"- {title}\n  Why useful for this task: {why}\n  Link: {link}")
    text = "\n".join(lines).strip()
    return DecisionReport(should_notify=True, report_text=_compact_report_text(text))


def _compact_report_text(text: Optional[str], max_chars: int = 3000) -> Optional[str]:
    """Compact and normalize report text to a maximum number of characters.

    :param text: The raw report text or ``None``.
    :param max_chars: Maximum characters allowed (default 3000).
    :returns: The normalized, possibly truncated text, or ``None``.
    """
    if not text:
        return text
    t = str(text)
    # Normalize whitespace and limit lines
    t = "\n".join([ln.strip() for ln in t.splitlines() if ln.strip()])
    if len(t) > max_chars:
        t = t[: max_chars - 3].rstrip() + "..."
    return t


def _why_for_task(task_query: str, summary: str, max_len: int = 220) -> str:
    """Heuristic one-liner explaining usefulness for the task.

    Prefers overlap of task terms with summary; falls back to the first sentence.

    :param task_query: The user task description.
    :param summary: Candidate summary to inspect.
    :param max_len: Maximum length of the produced sentence (default 220).
    :returns: A concise explanation string.
    """
    import re

    def toks(s: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9\-]+", s.lower())

    task_terms = set(toks(task_query)) - {
        "the",
        "and",
        "or",
        "of",
        "to",
        "for",
        "a",
        "in",
    }
    sent = (summary or "").strip().split(". ")[0]
    overlaps = [w for w in toks(sent) if w in task_terms]
    if overlaps:
        unique = []
        for w in overlaps:
            if w not in unique:
                unique.append(w)
        phrase = ", ".join(unique[:3])
        text = f"addresses {phrase} relevant to your task"
    else:
        text = sent or "directly related methods and findings"
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text
