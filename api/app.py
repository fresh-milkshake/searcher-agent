"""FastAPI application exposing the research pipeline as a REST API.

This module provides a thin HTTP layer over the internal agent pipeline in
:mod:`agent.pipeline`. It defines request/response models and endpoints that
delegate execution to :func:`agent.pipeline.pipeline.run_pipeline`.

- ``GET /healthz``: liveness probe
- ``POST /v1/run``: run the end-to-end research pipeline for a free-text task

See also: :mod:`agent.pipeline.models`, :mod:`agent.pipeline.pipeline`.
"""

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent.pipeline.models import (
    AnalysisResult,
    PipelineOutput,
    PipelineTask,
    ScoredAnalysis,
)
import agent.pipeline.pipeline as pipeline_mod


class PipelineTaskRequest(BaseModel):
    """Request schema for running the research pipeline.

    This mirrors :class:`agent.pipeline.models.PipelineTask` and is validated
    before being converted to the internal model.

    :ivar query: Free-text task description (e.g. "AI for medical imaging").
    :ivar categories: Optional arXiv categories (e.g. ["cs.AI", "cs.CV"]).
    :ivar max_queries: Upper bound on generated search queries (default 5).
    :ivar bm25_top_k: Number of top-ranked candidates to keep (default 20).
    :ivar max_analyze: Maximum number of candidates to analyze (default 10).
    :ivar min_relevance: Minimum relevance threshold in [0, 100] (default 50.0).
    """

    query: str = Field(min_length=1, description="Free-text task description")
    categories: Optional[List[str]] = Field(
        default=None, description="Optional arXiv categories"
    )
    max_queries: int = Field(default=5, ge=1, le=20)
    bm25_top_k: int = Field(default=20, ge=5, le=100)
    max_analyze: int = Field(default=10, ge=1, le=50)
    min_relevance: float = Field(default=50.0, ge=0.0, le=100.0)
    queries: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional user-suggested queries. The agent will decide sources per query."
        ),
    )


class PaperSummary(BaseModel):
    """Compact representation of an analyzed paper for API responses.

    This is a projection of :class:`agent.pipeline.models.AnalysisResult` used
    by the public API to keep responses concise.

    :ivar arxiv_id: Stable arXiv identifier (e.g. "2301.01234").
    :ivar title: Paper title.
    :ivar relevance: Relevance score in [0, 100].
    :ivar summary: Short summary tailored to the user task.
    :ivar link: Preferred URL (abstract or PDF).
    """

    arxiv_id: str
    title: str
    relevance: float
    summary: str
    link: Optional[str]


class RunResponse(BaseModel):
    """Response schema returned by the main pipeline endpoint.

    Aggregates a compact view of :class:`agent.pipeline.models.PipelineOutput`.

    :ivar task: Echo of the validated request payload.
    :ivar generated_queries: Queries produced by the strategy stage.
    :ivar analyzed: List of compact paper summaries.
    :ivar selected: Short list of selected items recommended for reporting.
    :ivar should_notify: Whether notifying the user is recommended.
    :ivar report_text: Plain-text report with findings, when available.
    """

    task: PipelineTaskRequest
    generated_queries: List[str]
    analyzed: List[PaperSummary]
    selected: List[PaperSummary]
    should_notify: bool
    report_text: Optional[str]


def _to_paper_summary(item: AnalysisResult) -> PaperSummary:
    """Convert an analysis result into a public paper summary.

    :param item: A single :class:`agent.pipeline.models.AnalysisResult` produced
                 by the analysis stage.
    :returns: A :class:`PaperSummary` with essential, serializable fields.
    """

    link = item.candidate.abs_url or item.candidate.pdf_url
    return PaperSummary(
        arxiv_id=item.candidate.arxiv_id,
        title=item.candidate.title,
        relevance=float(item.relevance),
        summary=item.summary,
        link=link,
    )


def _selected_to_summary(items: List[ScoredAnalysis]) -> List[PaperSummary]:
    """Convert selected scored analyses into compact summaries.

    :param items: Items returned by
                  :func:`agent.pipeline.decision.select_top`.
    :returns: List of :class:`PaperSummary` items.
    """

    summaries: List[PaperSummary] = []
    for s in items:
        summaries.append(_to_paper_summary(s.result))
    return summaries


app = FastAPI(title="Research AI API", version="0.1.0")


@app.get("/healthz")
async def health() -> dict[str, str]:
    """Liveness probe endpoint.

    :returns: A constant payload ``{"status": "ok"}`` when the service is
              alive.
    """

    return {"status": "ok"}


@app.post("/v1/run", response_model=RunResponse)
async def run(task: PipelineTaskRequest) -> RunResponse:
    """Run the research pipeline and return a compact response.

    The request is validated and transformed to
    :class:`agent.pipeline.models.PipelineTask`, then executed by
    :func:`agent.pipeline.pipeline.run_pipeline`.

    :param task: Validated request body describing the user's research task.
    :returns: A :class:`RunResponse` with generated queries, analyzed items,
              selection, decision flag, and optional report text.
    :raises fastapi.HTTPException: ``422 Unprocessable Entity`` if validation
            fails.
    """

    try:
        pipeline_task = PipelineTask.model_validate(task.model_dump())
    except Exception as error:  # pragma: no cover - pydantic will give details
        raise HTTPException(status_code=422, detail=str(error))

    output: PipelineOutput = await pipeline_mod.run_pipeline(pipeline_task)

    analyzed_summaries = [_to_paper_summary(a) for a in output.analyzed]
    selected_summaries = _selected_to_summary(output.selected)

    response = RunResponse(
        task=task,
        generated_queries=output.generated_queries,
        analyzed=analyzed_summaries,
        selected=selected_summaries,
        should_notify=output.should_notify,
        report_text=output.report_text,
    )
    return response
