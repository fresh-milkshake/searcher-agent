"""Database models."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Float,
    BigInteger,
    Integer,
    ForeignKey,
    Boolean,
    DateTime,
    Index,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from .enums import UserPlan, TaskStatus


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models."""

    pass


# Core User Management Models


class User(Base):
    """User model with plan management and rate limiting."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Plan and limits
    plan: Mapped[UserPlan] = mapped_column(String(20), default=UserPlan.FREE)
    daily_task_limit: Mapped[int] = mapped_column(
        Integer, default=5
    )  # Free: 5, Premium: 100
    concurrent_task_limit: Mapped[int] = mapped_column(
        Integer, default=1
    )  # Free: 1, Premium: 5

    # Counters (reset daily)
    daily_tasks_created: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_reset: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Billing
    plan_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    tasks: Mapped[List["UserTask"]] = relationship(back_populates="user", lazy="select")
    rate_limit_records: Mapped[List["RateLimitRecord"]] = relationship(
        back_populates="user", lazy="select"
    )


class RateLimitRecord(Base):
    """Rate limiting records for anti-spam protection."""

    __tablename__ = "rate_limit_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    action_type: Mapped[str] = mapped_column(
        String(50)
    )  # "task_create", "command", "message"

    # Rate limiting windows
    count_per_minute: Mapped[int] = mapped_column(Integer, default=0)
    count_per_hour: Mapped[int] = mapped_column(Integer, default=0)
    count_per_day: Mapped[int] = mapped_column(Integer, default=0)

    # Window reset times
    minute_reset_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    hour_reset_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    day_reset_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    last_action_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(
        back_populates="rate_limit_records", lazy="select"
    )

    __table_args__ = (Index("idx_user_action", "user_id", "action_type"),)


class TaskQueue(Base):
    """Global task queue with priority management."""

    __tablename__ = "task_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("user_task.id"), unique=True)

    # Queue management
    priority: Mapped[int] = mapped_column(
        Integer, default=100
    )  # Lower = higher priority, Premium users get lower numbers
    queue_position: Mapped[int] = mapped_column(Integer, default=0)
    estimated_start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Processing info
    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    task: Mapped["UserTask"] = relationship(back_populates="queue_entry", lazy="select")

    __table_args__ = (Index("idx_queue_priority", "priority", "created_at"),)


class TaskStatistics(Base):
    """Global task processing statistics for time estimation."""

    __tablename__ = "task_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Processing metrics
    total_tasks_processed: Mapped[int] = mapped_column(Integer, default=0)
    total_processing_time_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # Time metrics (in seconds)
    median_processing_time: Mapped[float] = mapped_column(
        Float, default=300.0
    )  # 5 minutes default
    avg_processing_time: Mapped[float] = mapped_column(Float, default=300.0)
    min_processing_time: Mapped[float] = mapped_column(Float, default=60.0)
    max_processing_time: Mapped[float] = mapped_column(Float, default=1800.0)

    # Queue metrics
    current_queue_length: Mapped[int] = mapped_column(Integer, default=0)
    active_workers: Mapped[int] = mapped_column(Integer, default=1)

    # Recent performance (last 24h)
    recent_completed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    recent_failed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    recent_avg_time: Mapped[float] = mapped_column(Float, default=300.0)

    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (Index("idx_last_updated", "last_updated"),)


class UserTask(Base):
    """Enhanced user task model with queue support."""

    __tablename__ = "user_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)

    # Enhanced status with queue support
    status: Mapped[TaskStatus] = mapped_column(String(20), default=TaskStatus.QUEUED)

    # Processing information
    cycles_completed: Mapped[int] = mapped_column(Integer, default=0)
    max_cycles: Mapped[int] = mapped_column(
        Integer, default=5
    )  # Free: 5, Premium: unlimited (set high)

    # Timing
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    estimated_completion_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Results
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships - Use eager loading to avoid lazy loading issues
    user: Mapped[User] = relationship(back_populates="tasks", lazy="select")
    queue_entry: Mapped[Optional[TaskQueue]] = relationship(
        back_populates="task",
        uselist=False,
        lazy="select",  # Use eager loading instead of lazy
    )

    __table_args__ = (
        Index("idx_user_status", "user_id", "status"),
        Index("idx_status_created", "status", "created_at"),
    )


class SearchQuery(Base):
    """Search queries for task processing."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Finding(Base):
    """Research findings from task processing."""

    __tablename__ = "finding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("user_task.id"))
    paper_id: Mapped[int] = mapped_column(ForeignKey("arxiv_paper.id"))
    relevance: Mapped[float] = mapped_column(Float)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# Legacy Models (Still used by agent system)


class ResearchTopic(Base):
    """Research topics for arXiv analysis."""

    __tablename__ = "research_topic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    target_topic: Mapped[str] = mapped_column(Text)
    search_area: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    analyses: Mapped[List["PaperAnalysis"]] = relationship(
        back_populates="topic", lazy="select"
    )


class ArxivPaper(Base):
    """ArXiv papers for analysis."""

    __tablename__ = "arxiv_paper"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    categories: Mapped[str] = mapped_column(Text)
    published: Mapped[datetime] = mapped_column(DateTime)
    updated: Mapped[datetime] = mapped_column(DateTime)
    pdf_url: Mapped[str] = mapped_column(Text)
    abs_url: Mapped[str] = mapped_column(Text)
    journal_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    analyses: Mapped[List["PaperAnalysis"]] = relationship(
        back_populates="paper", lazy="select"
    )


class PaperAnalysis(Base):
    """Analysis of paper relevance to research topics."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    paper: Mapped[ArxivPaper] = relationship(back_populates="analyses", lazy="select")
    topic: Mapped[ResearchTopic] = relationship(
        back_populates="analyses", lazy="select"
    )


class UserSettings(Base):
    """User settings for filtering and analysis."""

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

    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AgentStatus(Base):
    """Real-time agent status tracking."""

    __tablename__ = "agent_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(50), default="main_agent")
    status: Mapped[str] = mapped_column(String(50))
    activity: Mapped[str] = mapped_column(Text)
    current_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    current_topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    papers_processed: Mapped[int] = mapped_column(BigInteger, default=0)
    papers_found: Mapped[int] = mapped_column(BigInteger, default=0)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    session_start: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# Legacy models for backward compatibility (not actively used)


class Message(Base):
    """Legacy message model."""

    __tablename__ = "message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(50), default="user")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    tasks: Mapped[List["Task"]] = relationship(back_populates="message", lazy="select")


class Task(Base):
    """Legacy task model."""

    __tablename__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("message.id"), nullable=True
    )
    task_type: Mapped[str] = mapped_column(String(50))
    data: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    message: Mapped[Optional[Message]] = relationship(
        back_populates="tasks", lazy="select"
    )
