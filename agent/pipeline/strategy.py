"""Agentic strategy and query generation using ``output_type``.

Produces a :class:`QueryPlan` with structured :class:`GeneratedQuery` items.
"""

import os
from textwrap import dedent
from typing import List

from agents import Agent, Runner

from shared.llm import AGENT_MODEL
from shared.logger import get_logger
from .models import GeneratedQuery, PipelineTask, QueryPlan
from .utils import retry_async

logger = get_logger(__name__)

_STRATEGY_AGENT = Agent(
    name="Query Strategist",
    model=AGENT_MODEL,
    instructions=dedent(
        """
        You turn a user task into a compact set of boolean-friendly arXiv queries.
        - Prefer keyword-style queries (MUST/SHOULD/NOT via AND/OR/NOT, parentheses allowed)
        - Avoid redundancy between queries
        - Provide a short rationale per query
        - Respect optional category constraints
        - Keep the set small and high-precision
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

    prompt = dedent(
        f"""
        Task: {task.query}
        Categories: {", ".join(task.categories) if task.categories else "none"}
        Max queries: {task.max_queries}

        Produce up to {task.max_queries} focused queries with rationales.
        """
    )

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
        result = await retry_async(lambda: Runner.run(_STRATEGY_AGENT, prompt))
        plan_obj: QueryPlan = result.final_output
        num_q = len(plan_obj.queries) if getattr(plan_obj, "queries", None) else 0
        logger.info(f"Strategy agent produced {num_q} queries")
        if not getattr(plan_obj, "queries", None):
            raise ValueError("Empty plan")
        plan_obj.queries = plan_obj.queries[: task.max_queries]
        logger.debug(
            "Queries: " + "; ".join(q.query_text for q in plan_obj.queries[:5])
        )
        return plan_obj
    except Exception as error:
        logger.warning(f"Strategy agent failed, using heuristic fallback: {error}")
        base: str = task.query.strip()
        queries: List[GeneratedQuery] = [
            GeneratedQuery(query_text=base, rationale="Direct match to task"),
            GeneratedQuery(
                query_text=f"{base} AND (survey OR review)",
                rationale="Surveys and reviews",
            ),
            GeneratedQuery(
                query_text=f"{base} AND (benchmark OR dataset OR code)",
                rationale="Practical artifacts",
            ),
            GeneratedQuery(
                query_text=f"{base} NOT theory-only",
                rationale="Exclude purely theoretical work",
            ),
        ]
        fallback = QueryPlan(notes=None, queries=queries[: task.max_queries])
        logger.info(f"Heuristic produced {len(fallback.queries)} queries")
        return fallback
