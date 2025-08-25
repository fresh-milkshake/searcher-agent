"""Agentic strategy and query generation using ``output_type``.

Produces a :class:`QueryPlan` with structured :class:`GeneratedQuery` items.
"""

import os
from textwrap import dedent
from typing import List, Literal

from agents import Agent, Runner
from shared.llm import get_agent_model
from shared.logging import get_logger
from .models import GeneratedQuery, PipelineTask, QueryPlan
from .utils import retry_async

logger = get_logger(__name__)
SourceLiteral = Literal["arxiv", "scholar", "pubmed", "github"]


STRATEGY_AGENT = Agent(
    name="Query Strategist",
    model=get_agent_model(),
    instructions=dedent(
        """
        You turn a user task into a compact set of search queries. For EACH query,
        you must also choose the most relevant source among: arXiv, Google Scholar,
        PubMed, GitHub.

        - Prefer concise keyword-style queries
        - Avoid redundancy between queries
        - Provide a short rationale per query
        - If source=arXiv, boolean-style with AND/OR/NOT is welcome; optional category constraints may apply
        - If source=PubMed, prefer biomedical terms and common synonyms
        - If source=GitHub, qualifiers like language:Python, stars:>100 are welcome
        - Keep the set small and high-precision
        - Output JSON matching the provided schema, including the "source" field per query
        """
    ),
    output_type=QueryPlan,
)


async def generate_query_plan(task: PipelineTask) -> QueryPlan:
    """Invoke the strategy agent and return a structured query plan.

    Falls back gracefully to a deterministic heuristic if the agent returns
    nothing or invalid output.

    :param task: The pipeline task describing user intent and constraints.
    :returns: A :class:`QueryPlan` with up to ``task.max_queries`` queries.
    """

    # Provide compact JSON-like prompt with optional user-suggested queries
    import json

    payload = {
        "task": task.query,
        "categories": task.categories or [],
        "max_queries": task.max_queries,
        "suggested_queries": task.queries or [],
        "allowed_sources": ["arxiv", "scholar", "pubmed", "github"],
    }
    prompt = json.dumps(payload)

    logger.debug(
        f"Generating query plan (max={task.max_queries}, categories={task.categories})"
    )
    use_agents = os.getenv("PIPELINE_USE_AGENTS_STRATEGY", "1").lower() in {
        "1",
        "true",
        "yes",
    }
    if not use_agents:
        logger.info("Strategy agent disabled via env; using heuristic queries")
        raise Exception("strategy_agent_disabled")
    try:

        def _run_strategy_agent():
            return Runner.run(STRATEGY_AGENT, prompt)

        logger.info("Making a call to the strategy agent...")
        result = await retry_async(_run_strategy_agent, attempts=2, base_delay=0.5)
        plan_obj: QueryPlan = result.final_output
        num_q = len(plan_obj.queries) if getattr(plan_obj, "queries", None) else 0
        logger.info(f"Strategy agent produced {num_q} queries")
        if not getattr(plan_obj, "queries", None):
            raise ValueError("Empty plan")
        # Ensure source is present for each query; if missing, apply heuristic
        for q in plan_obj.queries:
            if not getattr(q, "source", None):
                # Heuristic fallback per query
                text = (q.query_text or "").lower()
                if any(
                    k in text
                    for k in [
                        "clinical",
                        "biomedical",
                        "gene",
                        "protein",
                        "cancer",
                        "pubmed",
                    ]
                ):
                    q.source = "pubmed"
                elif any(
                    k in text
                    for k in [
                        "github",
                        "code",
                        "implementation",
                        "repo",
                        "repository",
                        "stars:",
                    ]
                ):
                    q.source = "github"
                elif any(
                    k in text
                    for k in ["survey", "review", "meta-analysis", "literature"]
                ):
                    q.source = "scholar"
                else:
                    q.source = "arxiv"
        plan_obj.queries = plan_obj.queries[: task.max_queries]
        logger.debug(
            "Queries: " + "; ".join(q.query_text for q in plan_obj.queries[:5])
        )
        return plan_obj
    except Exception as error:
        logger.warning(f"Strategy agent failed, using heuristic fallback: {error}")
        base: str = task.query.strip()

        def _infer_source(text: str) -> SourceLiteral:
            t = text.lower()
            if any(
                k in t
                for k in [
                    "clinical",
                    "biomedical",
                    "gene",
                    "protein",
                    "cancer",
                    "pubmed",
                ]
            ):
                return "pubmed"
            if any(
                k in t
                for k in [
                    "github",
                    "code",
                    "implementation",
                    "repo",
                    "repository",
                    "stars:",
                ]
            ):
                return "github"
            if any(k in t for k in ["survey", "review", "meta-analysis", "literature"]):
                return "scholar"
            return "arxiv"

        base_arxiv = GeneratedQuery(
            query_text=base,
            source=_infer_source(base),
            rationale="Direct match to task",
        )
        survey_q = GeneratedQuery(
            query_text=f"{base} AND (survey OR review)",
            source=_infer_source(base + " survey"),
            rationale="Surveys and reviews",
        )
        artifacts_q = GeneratedQuery(
            query_text=f"{base} AND (benchmark OR dataset OR code)",
            source=_infer_source(base + " code"),
            rationale="Practical artifacts",
        )
        exclude_theory_q = GeneratedQuery(
            query_text=f"{base} NOT theory-only",
            source=_infer_source(base),
            rationale="Exclude purely theoretical work",
        )
        queries: List[GeneratedQuery] = [
            base_arxiv,
            survey_q,
            artifacts_q,
            exclude_theory_q,
        ]
        fallback = QueryPlan(notes=None, queries=queries[: task.max_queries])
        logger.info(f"Heuristic produced {len(fallback.queries)} queries")
        return fallback
