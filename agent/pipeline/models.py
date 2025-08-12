"""Typed models for the research pipeline.

This module defines Pydantic models and light-weight data structures used
across the pipeline: input tasks, intermediate candidates, and outputs.
"""

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, field_validator


class PipelineTask(BaseModel):
    """A high-level pipeline task describing the user's research intent.

    Parameters
    ----------
    query:
        Free-text task description or target area.
    categories:
        Optional arXiv categories to constrain the search, e.g. ``["cs.AI"]``.
    max_queries:
        Upper bound on generated search queries. Default: 5.
    bm25_top_k:
        Number of top-ranked candidates to keep. Default: 20.
    max_analyze:
        Max number of candidates to analyze with LLM. Default: 10.
    min_relevance:
        Minimum score required for inclusion in the final selection. Default: 50.0.

    Examples
    --------
    .. code-block:: python

        PipelineTask(query="RAG for small datasets", categories=["cs.AI"])  # doctest: +ELLIPSIS
    """

    query: str
    categories: Optional[List[str]] = None
    max_queries: int = Field(default=5, ge=1, le=20)
    bm25_top_k: int = Field(default=20, ge=5, le=100)
    max_analyze: int = Field(default=10, ge=1, le=50)
    min_relevance: float = Field(default=50.0, ge=0.0, le=100.0)
    queries: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional user-suggested queries. The strategy agent will still decide"
            " sources for each query."
        ),
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Query must not be empty.")
        return value


class PaperCandidate(BaseModel):
    """A lightweight representation of a potential paper to evaluate.

    Notes
    -----
    The ``bm25_score`` is populated during ranking and defaults to 0.0.
    """

    arxiv_id: str
    title: str
    summary: str
    categories: List[str] = Field(default_factory=list)
    published: Optional[datetime] = None
    updated: Optional[datetime] = None
    pdf_url: Optional[str] = None
    abs_url: Optional[str] = None
    journal_ref: Optional[str] = None
    doi: Optional[str] = None
    comment: Optional[str] = None
    primary_category: Optional[str] = None

    bm25_score: float = 0.0


class AnalysisInput(BaseModel):
    """Selected, ranked input to the LLM for deep analysis."""

    candidate: PaperCandidate
    snippets: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Outcome of a single LLM analysis of a paper candidate."""

    candidate: PaperCandidate
    relevance: float
    summary: str
    key_fragments: Optional[str] = None
    contextual_reasoning: Optional[str] = None


class PipelineOutput(BaseModel):
    """Final output of the pipeline for consumer channels.

    Examples
    --------
    .. code-block:: python

        from agent.pipeline.pipeline import run_pipeline_sync
        out = run_pipeline_sync(PipelineTask(query="graph neural networks for molecules"))
        print(out.should_notify, len(out.analyzed))
    """

    task: PipelineTask
    analyzed: List[AnalysisResult]
    generated_queries: List[str]
    selected: List["ScoredAnalysis"] = Field(default_factory=list)
    should_notify: bool = False
    report_text: Optional[str] = None


class GeneratedQuery(BaseModel):
    """Structured query item produced by the strategy agent."""

    query_text: str
    source: Literal["arxiv", "scholar", "pubmed", "github"]
    rationale: Optional[str] = None
    categories: Optional[List[str]] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None


class QueryPlan(BaseModel):
    """Agentic query plan consisting of multiple queries and optional notes."""

    notes: Optional[str] = None
    queries: List[GeneratedQuery] = Field(default_factory=list)


class AnalysisAgentOutput(BaseModel):
    """Output schema for the analysis agent via ``output_type``."""

    relevance: float
    summary: str
    key_fragments: Optional[str] = None
    contextual_reasoning: Optional[str] = None


class TelegramSummary(BaseModel):
    """Output schema for Telegram formatting agent."""

    html: str


class ScoredAnalysis(BaseModel):
    """Analysis result with overall score used for decision making."""

    result: AnalysisResult
    overall_score: float
    reasoning: Optional[str] = None


class DecisionReport(BaseModel):
    """Decision agent output controlling whether to notify and the report text."""

    should_notify: bool
    report_text: Optional[str]
