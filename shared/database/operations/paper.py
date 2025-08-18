"""Paper operations."""

from datetime import datetime
from typing import Any, List, Optional, Tuple

from sqlalchemy import select, and_, func

from ..connection import SessionLocal
from ..models import ArxivPaper, PaperAnalysis, ResearchTopic


async def get_arxiv_paper_by_arxiv_id(arxiv_id: str) -> Optional[ArxivPaper]:
    """Get ArXiv paper by ArXiv ID.

    :param arxiv_id: ArXiv ID
    :returns: ArxivPaper instance or None
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(ArxivPaper).where(ArxivPaper.arxiv_id == arxiv_id)
        )
        return result.scalar_one_or_none()


async def create_arxiv_paper(data: dict[str, Any]) -> ArxivPaper:
    """Create an ArXiv paper.

    :param data: Paper data
    :returns: ArxivPaper instance
    """
    async with SessionLocal() as session:
        paper = ArxivPaper(**data)
        session.add(paper)
        await session.commit()
        await session.refresh(paper)
        return paper


async def has_paper_analysis(paper_id: int, topic_id: int) -> bool:
    """Check if paper analysis exists.

    :param paper_id: Paper ID
    :param topic_id: Topic ID
    :returns: True if analysis exists
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(func.count(PaperAnalysis.id)).where(
                and_(
                    PaperAnalysis.paper_id == paper_id,
                    PaperAnalysis.topic_id == topic_id,
                )
            )
        )
        count_val = result.scalar_one()
        return bool(count_val and count_val > 0)


async def create_paper_analysis(
    *,
    paper_id: int,
    topic_id: int,
    relevance: float,
    summary: Optional[str],
    status: str = "analyzed",
    key_fragments: Optional[str] = None,
    contextual_reasoning: Optional[str] = None,
) -> PaperAnalysis:
    """Create a paper analysis.

    :param paper_id: Paper ID
    :param topic_id: Topic ID
    :param relevance: Relevance score
    :param summary: Analysis summary
    :param status: Analysis status
    :param key_fragments: Key fragments
    :param contextual_reasoning: Contextual reasoning
    :returns: PaperAnalysis instance
    """
    async with SessionLocal() as session:
        analysis = PaperAnalysis(
            paper_id=paper_id,
            topic_id=topic_id,
            relevance=relevance,
            summary=summary,
            status=status,
            key_fragments=key_fragments,
            contextual_reasoning=contextual_reasoning,
        )
        session.add(analysis)
        await session.commit()
        await session.refresh(analysis)
        return analysis


async def list_new_analyses_since(
    last_id: int, min_overall: float
) -> List[PaperAnalysis]:
    """List new analyses since last ID.

    :param last_id: Last analysis ID
    :param min_overall: Minimum relevance score
    :returns: List of PaperAnalysis instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(PaperAnalysis)
            .where(
                and_(
                    PaperAnalysis.id > last_id,
                    PaperAnalysis.status == "analyzed",
                    PaperAnalysis.relevance >= min_overall,
                )
            )
            .order_by(PaperAnalysis.created_at.asc())
        )
        return list(result.scalars().all())


async def get_analysis_with_entities(
    analysis_id: int,
) -> Optional[Tuple[PaperAnalysis, ArxivPaper, ResearchTopic]]:
    """Get analysis with related entities.

    :param analysis_id: Analysis ID
    :returns: Tuple of (PaperAnalysis, ArxivPaper, ResearchTopic) or None
    """
    async with SessionLocal() as session:
        analysis = await session.get(PaperAnalysis, analysis_id)
        if analysis is None:
            return None
        paper = await session.get(ArxivPaper, analysis.paper_id)
        topic = await session.get(ResearchTopic, analysis.topic_id)
        if paper is None or topic is None:
            return None
        return analysis, paper, topic


async def mark_analysis_notified(analysis_id: int) -> None:
    """Mark analysis as notified.

    :param analysis_id: Analysis ID
    """
    async with SessionLocal() as session:
        analysis = await session.get(PaperAnalysis, analysis_id)
        if analysis is None:
            return
        analysis.status = "notified"
        analysis.updated_at = datetime.now()
        await session.commit()


async def mark_analysis_queued(analysis_id: int) -> None:
    """Mark analysis as queued.

    :param analysis_id: Analysis ID
    """
    async with SessionLocal() as session:
        analysis = await session.get(PaperAnalysis, analysis_id)
        if analysis is None:
            return
        analysis.status = "queued"
        analysis.updated_at = datetime.now()
        await session.commit()
