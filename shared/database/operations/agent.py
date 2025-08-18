"""Agent operations."""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, and_, func

from ..connection import SessionLocal
from ..models import AgentStatus, PaperAnalysis, ArxivPaper, ResearchTopic


async def update_agent_status(
    *,
    agent_id: str,
    status: str,
    activity: str,
    current_user_id: Optional[int] = None,
    current_topic_id: Optional[int] = None,
    papers_processed: int = 0,
    papers_found: int = 0,
) -> None:
    """Update agent status.

    :param agent_id: Agent ID
    :param status: Agent status
    :param activity: Agent activity
    :param current_user_id: Current user ID
    :param current_topic_id: Current topic ID
    :param papers_processed: Papers processed count
    :param papers_found: Papers found count
    """
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(AgentStatus)
                .where(AgentStatus.agent_id == agent_id)
                .order_by(AgentStatus.id.desc())
            )
            agent_status = result.scalars().first()
            if agent_status is None:
                agent_status = AgentStatus(
                    agent_id=agent_id,
                    status=status,
                    activity=activity,
                    current_user_id=current_user_id,
                    current_topic_id=current_topic_id,
                    papers_processed=papers_processed,
                    papers_found=papers_found,
                    session_start=datetime.now(),
                )
                session.add(agent_status)
            else:
                agent_status.status = status
                agent_status.activity = activity
                agent_status.current_user_id = current_user_id
                agent_status.current_topic_id = current_topic_id
                agent_status.papers_processed = papers_processed
                agent_status.papers_found = papers_found
                agent_status.last_activity = datetime.now()
                agent_status.updated_at = datetime.now()
            await session.commit()
    except Exception:
        # Avoid propagating exceptions from background status updates
        import traceback

        traceback.print_exc()


async def get_agent_status(agent_id: str) -> Optional[AgentStatus]:
    """Get agent status.

    :param agent_id: Agent ID
    :returns: AgentStatus instance or None
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(AgentStatus)
            .where(AgentStatus.agent_id == agent_id)
            .order_by(AgentStatus.id.desc())
        )
        return result.scalars().first()


async def count_analyses_for_user(user_id: int) -> int:
    """Count analyses for user.

    :param user_id: User ID
    :returns: Analysis count
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(func.count(PaperAnalysis.id))
            .join(ResearchTopic, PaperAnalysis.topic_id == ResearchTopic.id)
            .where(ResearchTopic.user_id == user_id)
        )
        return int(result.scalar_one() or 0)


async def count_relevant_analyses_for_user(user_id: int, min_overall: float) -> int:
    """Count relevant analyses for user.

    :param user_id: User ID
    :param min_overall: Minimum relevance score
    :returns: Relevant analysis count
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(func.count(PaperAnalysis.id))
            .join(ResearchTopic, PaperAnalysis.topic_id == ResearchTopic.id)
            .where(
                and_(
                    ResearchTopic.user_id == user_id,
                    PaperAnalysis.relevance >= min_overall,
                )
            )
        )
        return int(result.scalar_one() or 0)


async def list_recent_analyses_for_user(
    user_id: int, limit: int = 5
) -> List[Tuple[PaperAnalysis, ArxivPaper]]:
    """List recent analyses for user.

    :param user_id: User ID
    :param limit: Result limit
    :returns: List of (PaperAnalysis, ArxivPaper) tuples
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(PaperAnalysis, ArxivPaper)
            .join(ArxivPaper, PaperAnalysis.paper_id == ArxivPaper.id)
            .join(ResearchTopic, PaperAnalysis.topic_id == ResearchTopic.id)
            .where(ResearchTopic.user_id == user_id)
            .order_by(PaperAnalysis.created_at.desc())
            .limit(limit)
        )
        rows = result.all()
        return [(row[0], row[1]) for row in rows]


async def swap_user_active_topics(user_id: int) -> Optional[ResearchTopic]:
    """Swap user active topics.

    :param user_id: User ID
    :returns: ResearchTopic instance or None
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(
                and_(ResearchTopic.user_id == user_id, ResearchTopic.is_active)
            )
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            return None
        old_target = topic.target_topic
        topic.target_topic = topic.search_area
        topic.search_area = old_target
        topic.updated_at = datetime.now()
        await session.commit()
        await session.refresh(topic)
        return topic
