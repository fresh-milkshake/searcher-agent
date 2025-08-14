import asyncio
from typing import List

from shared.logging import get_logger

from .analyze import analyze_candidates
from .formatting import to_telegram_html
from .models import AnalysisInput, PipelineOutput, PipelineTask, GeneratedQuery
from .ranking import rank_candidates
from .search import collect_candidates, _broaden_query
from .decision import select_top, make_decision_and_report
from .strategy import generate_query_plan


logger = get_logger(__name__)


async def run_pipeline(task: PipelineTask) -> PipelineOutput:
    """Execute the end-to-end research pipeline and return structured output.

    Stages::

      1) Strategy: generate multiple queries for the task
      2) Retrieval: collect candidates from arXiv
      3) Ranking: score with BM25 over title+abstract
      4) Analysis: LLM/heuristic analysis of top candidates
      5) Decision: choose items and produce a report

    :param task: Validated :class:`agent.pipeline.models.PipelineTask` describing
                 user intent.
    :returns: Structured :class:`PipelineOutput` with analyzed items and an
              optional human report.
    """

    task = PipelineTask.model_validate(task)

    # Always run strategy to assign sources per query; include user-suggested queries as hints
    logger.info("Stage: strategy -> queries & sources")
    plan = await generate_query_plan(task)
    generated_queries: List[GeneratedQuery] = list(plan.queries)
    logger.info(f"Generated {len(generated_queries)} queries for task")

    # Retrieve candidates
    logger.info("Stage: retrieval -> multi-source")
    candidates = collect_candidates(task, generated_queries, per_query_limit=50)
    logger.info(f"Collected {len(candidates)} unique candidates")

    if not candidates:
        # Try broadening queries automatically
        broadened_gq: List[GeneratedQuery] = []
        for gq in generated_queries:
            for b in _broaden_query(gq.query_text):
                if not b:
                    continue
                broadened_gq.append(GeneratedQuery(query_text=b, source=gq.source))
        if broadened_gq:
            logger.warning(
                f"No candidates found; retrying with broadened queries (n={len(broadened_gq)})"
            )
            more = collect_candidates(task, broadened_gq, per_query_limit=50)
            # Merge
            candidates = more
            logger.info(
                f"Collected {len(candidates)} unique candidates after broadening"
            )

    # Rank with BM25
    logger.info("Stage: ranking -> BM25")
    ranked = rank_candidates(
        query=task.query, candidates=candidates, top_k=task.bm25_top_k
    )
    logger.info(f"Ranked and kept top {len(ranked)} candidates")

    # Build analysis inputs (context reduction: abstract only for now)
    analysis_inputs: List[AnalysisInput] = [
        AnalysisInput(candidate=c, snippets=[]) for c in ranked[: task.max_analyze]
    ]

    # Analyze with LLM
    logger.info("Stage: analysis -> LLM/heuristic")
    analyzed = await analyze_candidates(
        task_query=task.query, analysis_inputs=analysis_inputs
    )
    logger.info(f"Analyzed {len(analyzed)} candidates")

    # 6.2 Scoring and selection + 6.1 Summary/reporting decision (mandatory)
    selected = select_top(task, analyzed)
    decision = await make_decision_and_report(task, selected)

    return PipelineOutput(
        task=task,
        analyzed=analyzed,
        generated_queries=[q.query_text for q in generated_queries],
        selected=selected,
        should_notify=decision.should_notify,
        report_text=decision.report_text,
    )


def run_pipeline_sync(task: PipelineTask) -> PipelineOutput:
    """Run :func:`run_pipeline` synchronously.

    This helper creates and runs an event loop to execute the async pipeline in
    simple scripts or REPLs.

    :param task: The pipeline task to execute.
    :returns: The structured pipeline output.
    """

    return asyncio.run(run_pipeline(task))


if __name__ == "__main__":
    example = PipelineTask(query="ligand protein binding extraction from pdf files")
    out = run_pipeline_sync(example)
    print(to_telegram_html(out))
