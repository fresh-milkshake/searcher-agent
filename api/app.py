"""FastAPI application exposing the research pipeline as a REST API.

This module defines the web server, request/response models, and routes.
It relies on the existing `agent.pipeline` package and does not modify
other services.
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
    """Request schema for running the research pipeline."""

    query: str = Field(min_length=1, description="Free-text task description")
    categories: Optional[List[str]] = Field(
        default=None, description="Optional arXiv categories"
    )
    max_queries: int = Field(default=5, ge=1, le=20)
    bm25_top_k: int = Field(default=20, ge=5, le=100)
    max_analyze: int = Field(default=10, ge=1, le=50)
    min_relevance: float = Field(default=50.0, ge=0.0, le=100.0)


class PaperSummary(BaseModel):
    """Compact representation of an analyzed paper for API responses."""

    arxiv_id: str
    title: str
    relevance: float
    summary: str
    link: Optional[str]


class RunResponse(BaseModel):
    """Response schema returned by the main pipeline endpoint."""

    task: PipelineTaskRequest
    generated_queries: List[str]
    analyzed: List[PaperSummary]
    selected: List[PaperSummary]
    should_notify: bool
    report_text: Optional[str]


def _to_paper_summary(item: AnalysisResult) -> PaperSummary:
    """Convert an `AnalysisResult` into a `PaperSummary`."""

    link = item.candidate.abs_url or item.candidate.pdf_url
    return PaperSummary(
        arxiv_id=item.candidate.arxiv_id,
        title=item.candidate.title,
        relevance=float(item.relevance),
        summary=item.summary,
        link=link,
    )


def _selected_to_summary(items: List[ScoredAnalysis]) -> List[PaperSummary]:
    """Convert selected scored analyses into summaries."""

    summaries: List[PaperSummary] = []
    for s in items:
        summaries.append(_to_paper_summary(s.result))
    return summaries


app = FastAPI(title="Searcher Agent API", version="0.1.0")


@app.get("/healthz")
async def health() -> dict[str, str]:
    """Liveness probe endpoint."""

    return {"status": "ok"}


@app.post("/v1/run", response_model=RunResponse)
async def run(task: PipelineTaskRequest) -> RunResponse:  # noqa: A001 - endpoint name
    """Run the research pipeline and return a compact response."""

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
