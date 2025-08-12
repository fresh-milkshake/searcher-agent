"""Async SQLAlchemy database layer and models with helper functions.

This module defines the async engine, session factory, ORM models, and
convenience functions for common CRUD operations used by the app.
"""

import os
import json
from datetime import datetime
from typing import Any, Optional, Tuple, List

from sqlalchemy import (
    String,
    Text,
    Float,
    BigInteger,
    Integer,
    ForeignKey,
    select,
    func,
    and_,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(50), default="user")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    tasks: Mapped[list["Task"]] = relationship(back_populates="message")


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("message.id"), nullable=True
    )
    task_type: Mapped[str] = mapped_column(String(50))
    data: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    message: Mapped[Optional[Message]] = relationship(back_populates="tasks")


class ResearchTopic(Base):
    __tablename__ = "research_topic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    target_topic: Mapped[str] = mapped_column(Text)
    search_area: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    analyses: Mapped[list["PaperAnalysis"]] = relationship(back_populates="topic")


class ArxivPaper(Base):
    __tablename__ = "arxiv_paper"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    categories: Mapped[str] = mapped_column(Text)
    published: Mapped[datetime] = mapped_column()
    updated: Mapped[datetime] = mapped_column()
    pdf_url: Mapped[str] = mapped_column(Text)
    abs_url: Mapped[str] = mapped_column(Text)
    journal_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    analyses: Mapped[list["PaperAnalysis"]] = relationship(back_populates="paper")


class PaperAnalysis(Base):
    __tablename__ = "paper_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("arxiv_paper.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("research_topic.id"))

    relevance: Mapped[float] = mapped_column(Float)

    key_fragments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contextual_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    innovation_assessment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    practical_significance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    paper: Mapped[ArxivPaper] = relationship(back_populates="analyses")
    topic: Mapped[ResearchTopic] = relationship(back_populates="analyses")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)

    min_relevance: Mapped[float] = mapped_column(Float, default=50.0)

    instant_notification_threshold: Mapped[float] = mapped_column(Float, default=80.0)
    daily_digest_threshold: Mapped[float] = mapped_column(Float, default=50.0)
    weekly_digest_threshold: Mapped[float] = mapped_column(Float, default=30.0)

    group_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    days_back_to_search: Mapped[str] = mapped_column(String(10), default="7")
    excluded_categories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    monitoring_enabled: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)


class AgentStatus(Base):
    __tablename__ = "agent_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(50), default="main_agent")
    status: Mapped[str] = mapped_column(String(50))
    activity: Mapped[str] = mapped_column(Text)
    current_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    current_topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    papers_processed: Mapped[int] = mapped_column(BigInteger, default=0)
    papers_found: Mapped[int] = mapped_column(BigInteger, default=0)
    last_activity: Mapped[datetime] = mapped_column(default=datetime.now)
    session_start: Mapped[datetime] = mapped_column(default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def ensure_connection() -> None:
    # Async SQLAlchemy manages connections via the session. No-op retained for compatibility.
    return None


# Helper functions used throughout the app


async def create_task(
    task_type: str,
    data: dict[str, Any],
    status: str = "pending",
    result: Optional[str] = None,
) -> Task:
    async with SessionLocal() as session:
        task = Task(
            task_type=task_type, data=json.dumps(data), status=status, result=result
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def list_pending_tasks() -> list[Task]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Task).where(Task.status == "pending").order_by(Task.created_at.asc())
        )
        return list(result.scalars().all())


async def mark_task_completed(task_id: int, result_text: Optional[str]) -> None:
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return
        task.status = "completed"
        task.result = result_text
        task.updated_at = datetime.now()
        await session.commit()


async def mark_task_failed(task_id: int, error_text: str) -> None:
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return
        task.status = "failed"
        task.result = error_text
        task.updated_at = datetime.now()
        await session.commit()


async def list_completed_tasks_since(last_id: int) -> list[Task]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Task)
            .where(and_(Task.id > last_id, Task.status == "completed"))
            .order_by(Task.id.asc())
        )
        return list(result.scalars().all())


async def mark_task_sent(task_id: int) -> None:
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return
        task.status = "sent"
        task.updated_at = datetime.now()
        await session.commit()


async def get_task(task_id: int) -> Optional[Task]:
    async with SessionLocal() as session:
        return await session.get(Task, task_id)


async def get_user_settings(user_id: int) -> Optional[UserSettings]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()


async def get_or_create_user_settings(user_id: int) -> UserSettings:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(user_id=user_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def update_user_settings(user_id: int, **fields: Any) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(user_id=user_id)
            session.add(settings)
        for key, value in fields.items():
            setattr(settings, key, value)
        settings.updated_at = datetime.now()
        await session.commit()


async def deactivate_user_topics(user_id: int) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(
                and_(ResearchTopic.user_id == user_id, ResearchTopic.is_active)
            )
        )  # noqa: E712
        topics = result.scalars().all()
        for t in topics:
            t.is_active = False
            t.updated_at = datetime.now()
        await session.commit()


async def create_research_topic(
    user_id: int, target_topic: str, search_area: str
) -> ResearchTopic:
    async with SessionLocal() as session:
        topic = ResearchTopic(
            user_id=user_id,
            target_topic=target_topic,
            search_area=search_area,
            is_active=True,
        )
        session.add(topic)
        await session.commit()
        await session.refresh(topic)
        return topic


async def get_active_topic_by_user(user_id: int) -> Optional[ResearchTopic]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(
                and_(ResearchTopic.user_id == user_id, ResearchTopic.is_active)
            )  # noqa: E712
        )
        return result.scalar_one_or_none()


async def list_active_topics() -> list[ResearchTopic]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(ResearchTopic.is_active)
        )  # noqa: E712
        return list(result.scalars().all())


async def get_topic_by_user_and_text(
    user_id: int, target_topic: str, search_area: str
) -> Optional[ResearchTopic]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(
                and_(
                    ResearchTopic.user_id == user_id,
                    ResearchTopic.target_topic == target_topic,
                    ResearchTopic.search_area == search_area,
                )
            )
        )
        return result.scalar_one_or_none()


async def get_arxiv_paper_by_arxiv_id(arxiv_id: str) -> Optional[ArxivPaper]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ArxivPaper).where(ArxivPaper.arxiv_id == arxiv_id)
        )
        return result.scalar_one_or_none()


async def create_arxiv_paper(data: dict[str, Any]) -> ArxivPaper:
    async with SessionLocal() as session:
        paper = ArxivPaper(**data)
        session.add(paper)
        await session.commit()
        await session.refresh(paper)
        return paper


async def has_paper_analysis(paper_id: int, topic_id: int) -> bool:
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
) -> list[PaperAnalysis]:
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
    async with SessionLocal() as session:
        analysis = await session.get(PaperAnalysis, analysis_id)
        if analysis is None:
            return
        analysis.status = "notified"
        analysis.updated_at = datetime.now()
        await session.commit()


async def mark_analysis_queued(analysis_id: int) -> None:
    async with SessionLocal() as session:
        analysis = await session.get(PaperAnalysis, analysis_id)
        if analysis is None:
            return
        analysis.status = "queued"
        analysis.updated_at = datetime.now()
        await session.commit()


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
    async with SessionLocal() as session:
        result = await session.execute(
            select(AgentStatus)
            .where(AgentStatus.agent_id == agent_id)
            .order_by(AgentStatus.id.desc())
        )
        return result.scalars().first()


async def count_analyses_for_user(user_id: int) -> int:
    async with SessionLocal() as session:
        result = await session.execute(
            select(func.count(PaperAnalysis.id))
            .join(ResearchTopic, PaperAnalysis.topic_id == ResearchTopic.id)
            .where(ResearchTopic.user_id == user_id)
        )
        return int(result.scalar_one() or 0)


async def count_relevant_analyses_for_user(user_id: int, min_overall: float) -> int:
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
) -> list[Tuple[PaperAnalysis, ArxivPaper]]:
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
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(
                and_(ResearchTopic.user_id == user_id, ResearchTopic.is_active)
            )  # noqa: E712
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


# Task-driven assistant additions


class UserTask(Base):
    __tablename__ = "user_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|paused
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)


class SearchQuery(Base):
    __tablename__ = "search_query"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("user_task.id"))
    query_text: Mapped[str] = mapped_column(Text)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    categories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    time_from: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    time_to: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|disabled
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)


class Finding(Base):
    __tablename__ = "finding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("user_task.id"))
    paper_id: Mapped[int] = mapped_column(ForeignKey("arxiv_paper.id"))
    relevance: Mapped[float] = mapped_column(Float)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


async def create_user_task(user_id: int, title: str, description: str) -> UserTask:
    async with SessionLocal() as session:
        task = UserTask(
            user_id=user_id, title=title, description=description, status="active"
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def update_user_task_status(task_id: int, status: str) -> None:
    async with SessionLocal() as session:
        task = await session.get(UserTask, task_id)
        if task is None:
            return
        task.status = status
        task.updated_at = datetime.now()
        await session.commit()


async def get_user_tasks(user_id: int) -> list[UserTask]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .where(UserTask.user_id == user_id)
            .order_by(UserTask.created_at.desc())
        )
        return list(result.scalars().all())


async def update_user_task_status_for_user(
    user_id: int, task_id: int, status: str
) -> bool:
    """Safely update task status ensuring ownership by user. Returns True if updated."""
    async with SessionLocal() as session:
        task = await session.get(UserTask, task_id)
        if task is None or task.user_id != user_id:
            return False
        task.status = status
        task.updated_at = datetime.now()
        await session.commit()
        return True


async def deactivate_user_tasks(user_id: int) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask).where(
                and_(UserTask.user_id == user_id, UserTask.status == "active")
            )
        )
        tasks = result.scalars().all()
        for t in tasks:
            t.status = "paused"
            t.updated_at = datetime.now()
        await session.commit()


async def list_active_user_tasks() -> List[UserTask]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .where(UserTask.status == "active")
            .order_by(UserTask.created_at.asc())
        )
        return list(result.scalars().all())


async def get_most_recent_active_user_task() -> Optional[UserTask]:
    """Return the most recently updated active user task, or ``None`` if none exist.

    :returns: A single :class:`UserTask` instance or ``None`` when no active tasks.
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .where(UserTask.status == "active")
            .order_by(UserTask.updated_at.desc(), UserTask.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()


async def list_active_queries_for_task(task_id: int) -> List[SearchQuery]:
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
    async with SessionLocal() as session:
        f = Finding(
            task_id=task_id, paper_id=paper_id, relevance=relevance, summary=summary
        )
        session.add(f)
        await session.commit()
        await session.refresh(f)
        return f


async def list_user_tasks(user_id: int) -> List[UserTask]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .where(UserTask.user_id == user_id)
            .order_by(UserTask.created_at.desc())
        )
        return list(result.scalars().all())
