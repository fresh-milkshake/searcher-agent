"""Search query operations."""

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_

from ..connection import SessionLocal
from ..models import SearchQuery, Finding


async def list_active_queries_for_task(task_id: int) -> List[SearchQuery]:
    """List active search queries for a task.

    :param task_id: Task ID
    :returns: List of SearchQuery instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(SearchQuery)
            .where(and_(SearchQuery.task_id == task_id, SearchQuery.status == "active"))
            .order_by(
                SearchQuery.last_run_at.is_(None).desc(), SearchQuery.last_run_at.asc()
            )
        )
        return list(result.scalars().all())


async def create_search_query(
    *,
    task_id: int,
    query_text: str,
    rationale: Optional[str] = None,
    categories: Optional[List[str]] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    status: str = "active",
) -> SearchQuery:
    """Create a new search query.

    :param task_id: Task ID
    :param query_text: Search query text
    :param rationale: Query rationale
    :param categories: Search categories
    :param time_from: Time from
    :param time_to: Time to
    :param status: Query status
    :returns: SearchQuery instance
    """
    async with SessionLocal() as session:
        q = SearchQuery(
            task_id=task_id,
            query_text=query_text,
            rationale=rationale,
            categories=json.dumps(categories or []),
            time_from=time_from,
            time_to=time_to,
            status=status,
        )
        session.add(q)
        await session.commit()
        await session.refresh(q)
        return q


async def update_search_query_stats(query_id: int, success_increment: int = 0) -> None:
    """Update search query statistics.

    :param query_id: Query ID
    :param success_increment: Success count increment
    """
    async with SessionLocal() as session:
        q = await session.get(SearchQuery, query_id)
        if q is None:
            return
        q.last_run_at = datetime.now()
        if success_increment:
            q.success_count = int(q.success_count or 0) + success_increment
        q.updated_at = datetime.now()
        await session.commit()


async def record_finding(
    task_id: int, paper_id: int, relevance: float, summary: Optional[str]
) -> Finding:
    """Record a research finding.

    :param task_id: Task ID
    :param paper_id: Paper ID
    :param relevance: Relevance score
    :param summary: Finding summary
    :returns: Finding instance
    """
    async with SessionLocal() as session:
        f = Finding(
            task_id=task_id, paper_id=paper_id, relevance=relevance, summary=summary
        )
        session.add(f)
        await session.commit()
        await session.refresh(f)
        return f
