"""LLM-based analysis stage for ranked candidates.

This module provides a minimal async analysis function that:
- Reduces context (abstract only for now)
- Calls the shared LLM model once per paper
- Returns structured ``AnalysisResult`` instances
- Includes simple caching for performance optimization

Retries and concurrency limits can be layered in the orchestrator later.
"""

import os
from textwrap import dedent
from typing import List, Dict
import hashlib

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

# Simple in-memory cache for analysis results (task_query + arxiv_id -> AnalysisResult)
_analysis_cache: Dict[str, AnalysisResult] = {}
_max_cache_size = 1000  # Limit cache size to prevent memory issues


def _get_cache_key(task_query: str, arxiv_id: str) -> str:
    """Generate a cache key for the analysis result.

    :param task_query: The task description that guides relevance.
    :param arxiv_id: The paper's arXiv ID.
    :returns: A hash-based cache key.
    """
    combined = f"{task_query}|{arxiv_id}"
    return hashlib.md5(combined.encode()).hexdigest()


def _get_cached_analysis(task_query: str, arxiv_id: str) -> AnalysisResult | None:
    """Retrieve cached analysis result if available.

    :param task_query: The task description that guides relevance.
    :param arxiv_id: The paper's arXiv ID.
    :returns: Cached AnalysisResult or None if not found.
    """
    cache_key = _get_cache_key(task_query, arxiv_id)
    return _analysis_cache.get(cache_key)


def _cache_analysis(task_query: str, arxiv_id: str, result: AnalysisResult) -> None:
    """Cache an analysis result.

    :param task_query: The task description that guides relevance.
    :param arxiv_id: The paper's arXiv ID.
    :param result: The analysis result to cache.
    """
    global _analysis_cache

    # Simple cache size management - remove oldest entries if needed
    if len(_analysis_cache) >= _max_cache_size:
        # Remove 10% of oldest entries (simple FIFO-like approach)
        to_remove = max(1, _max_cache_size // 10)
        keys_to_remove = list(_analysis_cache.keys())[:to_remove]
        for key in keys_to_remove:
            del _analysis_cache[key]

    cache_key = _get_cache_key(task_query, arxiv_id)
    _analysis_cache[cache_key] = result


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
    """Analyze candidates via agents or a heuristic fallback with parallel processing.

    When an API key and the environment flag ``PIPELINE_USE_AGENTS_ANALYZE`` is
    set, uses the configured LLM agent to produce structured outputs.
    Otherwise, computes a quick overlap-based heuristic.

    :param task_query: The task description that guides relevance.
    :param analysis_inputs: Ranked inputs containing candidates and optional snippets.
    :returns: One :class:`AnalysisResult` per input, preserving order.
    """
    import asyncio

    has_api_key = bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"))
    use_agents = os.getenv("PIPELINE_USE_AGENTS_ANALYZE", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    max_concurrent = int(os.getenv("PIPELINE_MAX_CONCURRENT_ANALYSIS", "5"))

    logger.debug(
        f"Analyzing {len(analysis_inputs)} candidates (agent={'on' if use_agents and has_api_key else 'off'}, concurrent={max_concurrent})"
    )

    async def analyze_single_candidate(item: AnalysisInput) -> AnalysisResult:
        """Analyze a single candidate paper with caching support."""
        # Check cache first
        cached_result = _get_cached_analysis(task_query, item.candidate.arxiv_id)
        if cached_result is not None:
            logger.debug(f"Using cached analysis for {item.candidate.arxiv_id}")
            return cached_result

        if has_api_key and use_agents:
            try:
                prompt = _build_prompt(task_query, item.candidate, item.snippets)
                from agents import Runner

                run_result = await retry_async(
                    lambda: Runner.run(_get_analyzer(), prompt),
                    attempts=2,  # Reduced retry attempts for faster failure
                    base_delay=1.0,  # Reduced base delay
                )
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
                        logger.warning(
                            f"Failed to parse agent output as JSON: {parse_error}"
                        )
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

        # Create result and cache it
        result = AnalysisResult(
            candidate=item.candidate,
            relevance=float(relevance),
            summary=summary,
            key_fragments=key_fragments,
            contextual_reasoning=contextual_reasoning,
        )

        # Cache the result for future use
        _cache_analysis(task_query, item.candidate.arxiv_id, result)

        logger.debug(
            f"Analyzed {item.candidate.arxiv_id} relevance={float(relevance):.1f}"
        )
        return result

    # Create semaphore to limit concurrent LLM calls
    semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_with_semaphore(item: AnalysisInput) -> AnalysisResult:
        async with semaphore:
            return await analyze_single_candidate(item)

    # Process all candidates concurrently with controlled concurrency
    if use_agents and has_api_key:
        results = await asyncio.gather(
            *[analyze_with_semaphore(item) for item in analysis_inputs],
            return_exceptions=False,
        )
    else:
        # For heuristic mode, we can run all in parallel without limiting
        results = await asyncio.gather(
            *[analyze_single_candidate(item) for item in analysis_inputs],
            return_exceptions=False,
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
