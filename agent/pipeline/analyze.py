"""LLM-based analysis stage for ranked candidates.

This module provides a minimal async analysis function that:
- Reduces context (abstract only for now)
- Calls the shared LLM model once per paper
- Returns structured ``AnalysisResult`` instances

Retries and concurrency limits can be layered in the orchestrator later.
"""

import os
from textwrap import dedent
from typing import List

from shared.llm import get_agent_model
from .models import (
    AnalysisAgentOutput,
    AnalysisInput,
    AnalysisResult,
    PaperCandidate,
)
from shared.logging import get_logger
from .utils import retry_async

logger = get_logger(__name__)


def _get_analyzer():
    """Lazy initialization of the analyzer agent."""
    from agents import Agent
    return Agent(
        name="Paper Analyzer",
        model=get_agent_model(),
        instructions=dedent(
            """
            You are an expert research assistant. Given a paper's title and abstract,
            assess relevance to the user's task, write a concise summary, and return
            a percentage relevance.

            Return structured JSON.
            """
        ),
        output_type=AnalysisAgentOutput,
    )


def _build_prompt(
    task_query: str, candidate: PaperCandidate, snippets: List[str]
) -> str:
    """Build a compact analysis prompt for the LLM.

    :param task_query: The user task description used to judge relevance.
    :param candidate: The paper candidate to analyze.
    :param snippets: Optional extra text fragments to include (e.g., quotes).
    :returns: A compact prompt string for the analyzer agent.
    """
    text_snippets = "\n\n".join(snippets) if snippets else ""
    return dedent(
        f"""
        Task: {task_query}

        Title: {candidate.title}
        Abstract: {candidate.summary}

        Extra snippets:
        {text_snippets}
        """
    ).strip()


async def analyze_candidates(
    *, task_query: str, analysis_inputs: List[AnalysisInput]
) -> List[AnalysisResult]:
    """Analyze candidates via agents or a heuristic fallback.

    When an API key and the environment flag ``PIPELINE_USE_AGENTS_ANALYZE`` is
    set, uses the configured LLM agent to produce structured outputs.
    Otherwise, computes a quick overlap-based heuristic.

    :param task_query: The task description that guides relevance.
    :param analysis_inputs: Ranked inputs containing candidates and optional snippets.
    :returns: One :class:`AnalysisResult` per input, preserving order.
    """

    results: List[AnalysisResult] = []
    has_api_key = bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"))
    use_agents = os.getenv("PIPELINE_USE_AGENTS_ANALYZE", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    logger.debug(
        f"Analyzing {len(analysis_inputs)} candidates (agent={'on' if use_agents and has_api_key else 'off'})"
    )
    for item in analysis_inputs:
        if has_api_key and use_agents:
            try:
                prompt = _build_prompt(task_query, item.candidate, item.snippets)
                from agents import Runner
                run_result = await retry_async(lambda: Runner.run(_get_analyzer(), prompt))
                # Prefer parsed when available
                out = getattr(run_result, "parsed", None)
                if out is None:
                    # Fallback to manual parse
                    import json

                    raw = str(getattr(run_result, "final_output", "")).strip() or str(
                        run_result
                    )
                    try:
                        data = json.loads(raw)
                        out = AnalysisAgentOutput.model_validate(data)
                    except (json.JSONDecodeError, ValueError) as parse_error:
                        logger.warning(f"Failed to parse agent output as JSON: {parse_error}")
                        raise
                relevance = float(out.relevance)
                summary = str(out.summary).strip()
                key_fragments = out.key_fragments
                contextual_reasoning = out.contextual_reasoning
            except Exception as error:
                # Network/model failure: fallback to heuristic
                logger.warning(
                    f"Analyzer agent failed for {item.candidate.arxiv_id}: {error}"
                )
                relevance = _heuristic_relevance(task_query, item.candidate)
                summary = _truncate_summary(item.candidate.summary)
                key_fragments = None
                contextual_reasoning = None
        else:
            # No API key configured: heuristic mode
            relevance = _heuristic_relevance(task_query, item.candidate)
            summary = _truncate_summary(item.candidate.summary)
            key_fragments = None
            contextual_reasoning = None

        results.append(
            AnalysisResult(
                candidate=item.candidate,
                relevance=float(relevance),
                summary=summary,
                key_fragments=key_fragments,
                contextual_reasoning=contextual_reasoning,
            )
        )
        logger.debug(
            f"Analyzed {item.candidate.arxiv_id} relevance={float(relevance):.1f}"
        )
    return results


def _heuristic_relevance(task_query: str, candidate: PaperCandidate) -> float:
    """Compute a quick overlap-based relevance in ``[0, 100]``.

    :param task_query: The task description.
    :param candidate: The paper candidate.
    :returns: A score in the range ``[0, 100]``.
    """
    import re

    def toks(s: str) -> set[str]:
        return set(re.findall(r"\w+", s.lower()))

    q = toks(task_query)
    d = toks(f"{candidate.title} {candidate.summary}")
    if not q:
        return 0.0
    overlap = len(q & d) / max(len(q), 1)
    score = 100.0 * overlap
    # Lightly mix in bm25 if available
    score = 0.7 * score + 0.3 * max(0.0, min(100.0, candidate.bm25_score))
    return float(max(0.0, min(100.0, score)))


def _truncate_summary(text: str, max_chars: int = 800) -> str:
    """Return a summary truncated to a maximum number of characters.

    :param text: Source text to truncate.
    :param max_chars: Maximum number of characters to retain (default 800).
    :returns: The truncated summary string.
    """
    s = (text or "").strip()
    return s[:max_chars]
