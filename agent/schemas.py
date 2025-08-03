"""Structured output schemas for AI agents"""

from typing import Literal
from pydantic import BaseModel, Field


class TopicAnalysis(BaseModel):
    """Schema for topic presence analysis output"""

    topic_presence: float = Field(
        description="Topic presence percentage from 0 to 100", ge=0.0, le=100.0
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level in the assessment"
    )
    key_mentions: list[str] = Field(
        description="Key mentions or applications of the topic found",
        max_items=5,
        default_factory=list,
    )  # type: ignore
    reasoning: str = Field(
        description="Brief explanation of the topic presence score", max_length=100
    )


class AnalysisReport(BaseModel):
    """Schema for analysis report output"""

    summary: str = Field(
        description="Concise summary of the topic intersection (1-2 sentences)",
        max_length=300,
    )
    innovation_level: Literal["high", "medium", "low"] = Field(
        description="Assessment of the approach's innovativeness"
    )
    practical_significance: Literal["high", "medium", "low"] = Field(
        description="Assessment of practical significance"
    )
    key_applications: list[str] = Field(
        description="Key applications or methods mentioned",
        max_items=3,
        default_factory=list,
    )  # type: ignore
    recommendation: Literal[
        "highly_relevant", "relevant", "somewhat_relevant", "not_relevant"
    ] = Field(description="Overall recommendation based on the analysis")
