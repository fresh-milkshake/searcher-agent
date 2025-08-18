"""Database operations and helper functions."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple, List

from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from .connection import SessionLocal
from .models import (
    User,
    UserTask,
    RateLimitRecord,
    TaskQueue,
    TaskStatistics,
    SearchQuery,
    Finding,
    ResearchTopic,
    ArxivPaper,
    PaperAnalysis,
    UserSettings,
    AgentStatus,
    Task,
)
from .enums import UserPlan, TaskStatus


# User Management Operations


async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> User:
    """Get user by telegram_id or create new user with default free plan.

    :param telegram_id: Telegram user ID
    :param username: Telegram username (optional)
    :param first_name: User's first name (optional)
    :param last_name: User's last name (optional)
    :returns: User instance
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            # Set limits based on plan (FREE by default)
            daily_limit = 5  # Free plan default
            concurrent_limit = 1  # Free plan default

            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                plan=UserPlan.FREE,
                daily_task_limit=daily_limit,
                concurrent_task_limit=concurrent_limit,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # Update user info if provided
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True

            if updated:
                user.updated_at = datetime.now()
                await session.commit()
                await session.refresh(user)

        return user


async def upgrade_user_plan(
    telegram_id: int, plan: UserPlan, expires_at: Optional[datetime] = None
) -> bool:
    """Upgrade user plan and adjust limits.

    :param telegram_id: Telegram user ID
    :param plan: New plan type
    :param expires_at: Plan expiration date (for premium)
    :returns: True if upgraded successfully, False if user not found
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            return False

        user.plan = plan
        user.plan_expires_at = expires_at

        # Update limits based on plan
        if plan == UserPlan.PREMIUM:
            user.daily_task_limit = 100
            user.concurrent_task_limit = 5
        else:
            user.daily_task_limit = 5
            user.concurrent_task_limit = 1

        user.updated_at = datetime.now()
        await session.commit()
        return True


async def reset_daily_counters_if_needed(user: User) -> User:
    """Reset daily counters if a day has passed.

    :param user: User instance
    :returns: Updated user instance
    """
    now = datetime.now()
    if (now - user.last_daily_reset).days >= 1:
        async with SessionLocal() as session:
            # Re-fetch to avoid stale data
            fresh_user = await session.get(User, user.id)
            if fresh_user and (now - fresh_user.last_daily_reset).days >= 1:
                fresh_user.daily_tasks_created = 0
                fresh_user.last_daily_reset = now
                fresh_user.updated_at = now
                await session.commit()
                await session.refresh(fresh_user)
                return fresh_user
    return user


async def check_user_can_create_task(user: User) -> Tuple[bool, str]:
    """Check if user can create a new task based on limits.

    :param user: User instance
    :returns: Tuple of (can_create: bool, reason: str)
    """
    if user.is_banned:
        return False, f"Account banned: {user.ban_reason or 'Violation of terms'}"

    if not user.is_active:
        return False, "Account deactivated"

    # Check plan expiration for premium users
    if user.plan == UserPlan.PREMIUM and user.plan_expires_at:
        if datetime.now() > user.plan_expires_at:
            return False, "Premium plan expired"

    # Reset daily counters if needed
    user = await reset_daily_counters_if_needed(user)

    # Check daily limit
    if user.daily_tasks_created >= user.daily_task_limit:
        return False, f"Daily task limit reached ({user.daily_task_limit})"

    # Check concurrent tasks
    async with SessionLocal() as session:
        active_count = await session.execute(
            select(func.count(UserTask.id)).where(
                and_(
                    UserTask.user_id == user.id,
                    UserTask.status.in_([TaskStatus.QUEUED, TaskStatus.PROCESSING]),
                )
            )
        )
        active_tasks = active_count.scalar_one() or 0

        if active_tasks >= user.concurrent_task_limit:
            return (
                False,
                f"Concurrent task limit reached ({user.concurrent_task_limit})",
            )

    return True, "OK"


# Rate Limiting Operations


async def check_rate_limit(user_id: int, action_type: str) -> Tuple[bool, str]:
    """Check if user action is within rate limits.

    :param user_id: Internal user ID (not telegram_id)
    :param action_type: Type of action being performed
    :returns: Tuple of (allowed: bool, reason: str)
    """
    now = datetime.now()

    # Rate limits by action type
    limits = {
        "task_create": {"minute": 2, "hour": 10, "day": 50},
        "command": {"minute": 10, "hour": 100, "day": 500},
        "message": {"minute": 20, "hour": 200, "day": 1000},
    }

    action_limits = limits.get(action_type, limits["message"])

    async with SessionLocal() as session:
        result = await session.execute(
            select(RateLimitRecord).where(
                and_(
                    RateLimitRecord.user_id == user_id,
                    RateLimitRecord.action_type == action_type,
                )
            )
        )
        record = result.scalar_one_or_none()

        if record is None:
            # Create new rate limit record
            record = RateLimitRecord(
                user_id=user_id,
                action_type=action_type,
                count_per_minute=1,
                count_per_hour=1,
                count_per_day=1,
            )
            session.add(record)
            await session.commit()
            return True, "OK"

        # Reset counters if time windows have passed
        if (now - record.minute_reset_at).total_seconds() >= 60:
            record.count_per_minute = 0
            record.minute_reset_at = now

        if (now - record.hour_reset_at).total_seconds() >= 3600:
            record.count_per_hour = 0
            record.hour_reset_at = now

        if (now - record.day_reset_at).total_seconds() >= 86400:
            record.count_per_day = 0
            record.day_reset_at = now

        # Check limits
        if record.count_per_minute >= action_limits["minute"]:
            return (
                False,
                f"Rate limit exceeded: {action_limits['minute']} {action_type} per minute",
            )
        if record.count_per_hour >= action_limits["hour"]:
            return (
                False,
                f"Rate limit exceeded: {action_limits['hour']} {action_type} per hour",
            )
        if record.count_per_day >= action_limits["day"]:
            return (
                False,
                f"Rate limit exceeded: {action_limits['day']} {action_type} per day",
            )

        # Increment counters
        record.count_per_minute += 1
        record.count_per_hour += 1
        record.count_per_day += 1
        record.last_action_at = now
        record.updated_at = now

        await session.commit()
        return True, "OK"


# Queue Management Operations


async def add_task_to_queue(task: UserTask) -> TaskQueue:
    """Add task to processing queue with appropriate priority.

    :param task: UserTask instance to queue
    :returns: TaskQueue entry
    """
    async with SessionLocal() as session:
        # Get user to determine priority
        user = await session.get(User, task.user_id)
        priority = 50 if user and user.plan == UserPlan.PREMIUM else 100

        # Calculate queue position
        queue_count = await session.execute(
            select(func.count(TaskQueue.id)).where(TaskQueue.task_id != task.id)
        )
        position = (queue_count.scalar_one() or 0) + 1

        # Estimate start time based on queue and processing stats
        stats = await get_or_create_task_statistics()
        estimated_wait = (
            stats.median_processing_time * (position - 1) / max(stats.active_workers, 1)
        )
        estimated_start = datetime.now() + timedelta(seconds=estimated_wait)

        queue_entry = TaskQueue(
            task_id=task.id,
            priority=priority,
            queue_position=position,
            estimated_start_time=estimated_start,
        )

        session.add(queue_entry)
        await session.commit()
        await session.refresh(queue_entry)

        # Update queue positions for all tasks
        await update_queue_positions()

        return queue_entry


async def update_queue_positions() -> None:
    """Update queue positions for all pending tasks based on priority and creation time."""
    async with SessionLocal() as session:
        # Get all queued tasks ordered by priority and creation time
        result = await session.execute(
            select(TaskQueue)
            .join(UserTask)
            .where(UserTask.status == TaskStatus.QUEUED)
            .order_by(TaskQueue.priority.asc(), TaskQueue.created_at.asc())
        )

        queue_entries = result.scalars().all()

        for i, entry in enumerate(queue_entries, 1):
            entry.queue_position = i
            # Update estimated start time
            stats = await get_or_create_task_statistics()
            estimated_wait = (
                stats.median_processing_time * (i - 1) / max(stats.active_workers, 1)
            )
            entry.estimated_start_time = datetime.now() + timedelta(
                seconds=estimated_wait
            )
            entry.updated_at = datetime.now()

        await session.commit()


async def get_next_task_from_queue() -> Optional[UserTask]:
    """Get next task from queue for processing.

    :returns: Next UserTask to process or None if queue is empty
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .join(TaskQueue)
            .where(UserTask.status == TaskStatus.QUEUED)
            .order_by(TaskQueue.priority.asc(), TaskQueue.created_at.asc())
            .limit(1)
        )

        return result.scalar_one_or_none()


# Task Statistics Operations


async def get_or_create_task_statistics() -> TaskStatistics:
    """Get current task statistics or create default if none exist.

    :returns: TaskStatistics instance
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(TaskStatistics).order_by(TaskStatistics.id.desc()).limit(1)
        )
        stats = result.scalar_one_or_none()

        if stats is None:
            stats = TaskStatistics()
            session.add(stats)
            await session.commit()
            await session.refresh(stats)

        return stats


async def update_task_statistics(
    processing_time_seconds: float, success: bool = True
) -> None:
    """Update global task processing statistics.

    :param processing_time_seconds: Time taken to process the task
    :param success: Whether the task completed successfully
    """
    async with SessionLocal() as session:
        stats = await get_or_create_task_statistics()

        # Update counts
        if success:
            stats.total_tasks_processed += 1
            stats.recent_completed_tasks += 1
            stats.total_processing_time_seconds += int(processing_time_seconds)
        else:
            stats.recent_failed_tasks += 1

        # Recalculate averages
        if stats.total_tasks_processed > 0:
            stats.avg_processing_time = (
                stats.total_processing_time_seconds / stats.total_tasks_processed
            )

        # Update min/max times
        if success:
            stats.min_processing_time = min(
                stats.min_processing_time, processing_time_seconds
            )
            stats.max_processing_time = max(
                stats.max_processing_time, processing_time_seconds
            )

            # Simple median estimation (can be improved with more sophisticated approach)
            recent_times = [
                stats.min_processing_time,
                processing_time_seconds,
                stats.max_processing_time,
            ]
            stats.median_processing_time = sorted(recent_times)[1]

            # Update recent average
            if stats.recent_completed_tasks > 0:
                stats.recent_avg_time = (
                    stats.recent_avg_time + processing_time_seconds
                ) / 2

        # Update queue length
        queue_count = await session.execute(select(func.count(TaskQueue.id)))
        stats.current_queue_length = queue_count.scalar_one() or 0

        stats.last_updated = datetime.now()
        await session.commit()


# Enhanced Task Management Operations


async def create_user_task_with_queue(
    user: User, description: str
) -> Tuple[UserTask, TaskQueue]:
    """Create a new user task and add it to the processing queue.

    :param user: User instance
    :param description: Task description
    :returns: Tuple of (UserTask, TaskQueue)
    """
    async with SessionLocal() as session:
        # Determine max cycles based on plan
        max_cycles = 100 if user.plan == UserPlan.PREMIUM else 5

        # Create task
        task = UserTask(
            user_id=user.id,
            title=description[:100] + "..." if len(description) > 100 else description,
            description=description,
            status=TaskStatus.QUEUED,
            max_cycles=max_cycles,
        )

        session.add(task)
        await session.commit()
        await session.refresh(task)

        # Add to queue
        queue_entry = await add_task_to_queue(task)

        # Increment user's daily counter
        user.daily_tasks_created += 1
        user.updated_at = datetime.now()
        await session.merge(user)
        await session.commit()

        return task, queue_entry


async def get_user_tasks(user_id: int) -> List[UserTask]:
    """Get all tasks for a user with eager loading to avoid lazy loading issues.

    :param user_id: Internal user ID
    :returns: List of UserTask instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .options(selectinload(UserTask.queue_entry))  # Eager load queue_entry
            .where(UserTask.user_id == user_id)
            .order_by(UserTask.created_at.desc())
        )
        return list(result.scalars().all())


async def update_user_task_status(task_id: int, status: TaskStatus) -> None:
    """Update task status.

    :param task_id: Task ID
    :param status: New status
    """
    async with SessionLocal() as session:
        task = await session.get(UserTask, task_id)
        if task is None:
            return
        task.status = status
        task.updated_at = datetime.now()
        await session.commit()


async def update_user_task_status_for_user(
    user_id: int, task_id: int, status: TaskStatus
) -> bool:
    """Safely update task status ensuring ownership by user.

    :param user_id: Internal user ID
    :param task_id: Task ID
    :param status: New status
    :returns: True if updated successfully, False if user not found
    """
    async with SessionLocal() as session:
        task = await session.get(UserTask, task_id)
        if task is None or task.user_id != user_id:
            return False
        task.status = status
        task.updated_at = datetime.now()
        await session.commit()
        return True


async def deactivate_user_tasks(user_id: int) -> None:
    """Deactivate all active tasks for a user.

    :param user_id: Internal user ID
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask).where(
                and_(UserTask.user_id == user_id, UserTask.status == TaskStatus.ACTIVE)
            )
        )
        tasks = result.scalars().all()
        for t in tasks:
            t.status = TaskStatus.PAUSED
            t.updated_at = datetime.now()
        await session.commit()


async def list_active_user_tasks() -> List[UserTask]:
    """List all active user tasks.

    :returns: List of active UserTask instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .where(UserTask.status == TaskStatus.ACTIVE)
            .order_by(UserTask.created_at.asc())
        )
        return list(result.scalars().all())


async def get_most_recent_active_user_task() -> Optional[UserTask]:
    """Return the most recently updated active user task, or None if none exist.

    :returns: A single UserTask instance or None when no active tasks.
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .where(UserTask.status == TaskStatus.ACTIVE)
            .order_by(UserTask.updated_at.desc(), UserTask.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()


async def list_user_tasks(user_id: int) -> List[UserTask]:
    """List all tasks for a user.

    :param user_id: Internal user ID
    :returns: List of UserTask instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .where(UserTask.user_id == user_id)
            .order_by(UserTask.created_at.desc())
        )
        return list(result.scalars().all())


# Search Query Operations


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


# Legacy Operations (for agent compatibility)


async def get_user_settings(user_id: int) -> Optional[UserSettings]:
    """Get user settings.

    :param user_id: User ID
    :returns: UserSettings instance or None
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()


async def get_or_create_user_settings(user_id: int) -> UserSettings:
    """Get or create user settings.

    :param user_id: User ID
    :returns: UserSettings instance
    """
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
    """Update user settings.

    :param user_id: User ID
    :param fields: Fields to update
    """
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
    """Deactivate all user topics.

    :param user_id: User ID
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(
                and_(ResearchTopic.user_id == user_id, ResearchTopic.is_active)
            )
        )
        topics = result.scalars().all()
        for t in topics:
            t.is_active = False
            t.updated_at = datetime.now()
        await session.commit()


async def create_research_topic(
    user_id: int, target_topic: str, search_area: str
) -> ResearchTopic:
    """Create a research topic.

    :param user_id: User ID
    :param target_topic: Target topic
    :param search_area: Search area
    :returns: ResearchTopic instance
    """
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
    """Get active topic for user.

    :param user_id: User ID
    :returns: ResearchTopic instance or None
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(
                and_(ResearchTopic.user_id == user_id, ResearchTopic.is_active)
            )
        )
        return result.scalar_one_or_none()


async def list_active_topics() -> List[ResearchTopic]:
    """List all active topics.

    :returns: List of ResearchTopic instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(ResearchTopic).where(ResearchTopic.is_active)
        )
        return list(result.scalars().all())


async def get_topic_by_user_and_text(
    user_id: int, target_topic: str, search_area: str
) -> Optional[ResearchTopic]:
    """Get topic by user and text.

    :param user_id: User ID
    :param target_topic: Target topic
    :param search_area: Search area
    :returns: ResearchTopic instance or None
    """
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


# Generic Task Operations (Legacy)


async def create_task(
    task_type: str,
    data: dict[str, Any],
    status: str = "pending",
    result: Optional[str] = None,
) -> Task:
    """Create a generic task.

    :param task_type: Task type
    :param data: Task data
    :param status: Task status
    :param result: Task result
    :returns: Task instance
    """
    async with SessionLocal() as session:
        task = Task(
            task_type=task_type, data=json.dumps(data), status=status, result=result
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def list_pending_tasks() -> List[Task]:
    """List pending tasks.

    :returns: List of Task instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Task).where(Task.status == "pending").order_by(Task.created_at.asc())
        )
        return list(result.scalars().all())


async def mark_task_completed(task_id: int, result_text: Optional[str]) -> None:
    """Mark task as completed.

    :param task_id: Task ID
    :param result_text: Result text
    """
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return
        task.status = "completed"
        task.result = result_text
        task.updated_at = datetime.now()
        await session.commit()


async def mark_task_failed(task_id: int, error_text: str) -> None:
    """Mark task as failed.

    :param task_id: Task ID
    :param error_text: Error text
    """
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return
        task.status = "failed"
        task.result = error_text
        task.updated_at = datetime.now()
        await session.commit()


async def list_completed_tasks_since(last_id: int) -> List[Task]:
    """List completed tasks since last ID.

    :param last_id: Last task ID
    :returns: List of Task instances
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Task)
            .where(and_(Task.id > last_id, Task.status == "completed"))
            .order_by(Task.id.asc())
        )
        return list(result.scalars().all())


async def mark_task_sent(task_id: int) -> None:
    """Mark task as sent.

    :param task_id: Task ID
    """
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return
        task.status = "sent"
        task.updated_at = datetime.now()
        await session.commit()


async def get_task(task_id: int) -> Optional[Task]:
    """Get task by ID.

    :param task_id: Task ID
    :returns: Task instance or None
    """
    async with SessionLocal() as session:
        return await session.get(Task, task_id)


# Integration Layer Between Bot and Agent Systems


async def get_next_queued_task() -> Optional[UserTask]:
    """Get next task from queue for agent processing.

    This function bridges the new UserTask/TaskQueue system with the agent.

    :returns: Next UserTask ready for processing or None if queue is empty
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTask)
            .join(TaskQueue)
            .where(UserTask.status == TaskStatus.QUEUED)
            .order_by(TaskQueue.priority.asc(), TaskQueue.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def start_task_processing(task_id: int) -> bool:
    """Start processing a queued task.

    Updates task status to PROCESSING and records start time.

    :param task_id: Task ID
    :returns: True if successfully started, False if task not found or already processing
    """
    async with SessionLocal() as session:
        task = await session.get(UserTask, task_id)
        if task is None or task.status != TaskStatus.QUEUED:
            return False

        task.status = TaskStatus.PROCESSING
        task.processing_started_at = datetime.now()
        task.updated_at = datetime.now()

        # Update queue entry if it exists
        queue_result = await session.execute(
            select(TaskQueue).where(TaskQueue.task_id == task.id)
        )
        queue_entry = queue_result.scalar_one_or_none()
        if queue_entry:
            queue_entry.started_at = datetime.now()
            queue_entry.updated_at = datetime.now()

        await session.commit()
        return True


async def complete_task_processing(
    task_id: int, success: bool = True, error_message: Optional[str] = None
) -> bool:
    """Complete task processing and update status.

    :param task_id: Task ID
    :param success: Whether task completed successfully
    :param error_message: Error message if task failed
    :returns: True if successfully completed
    """
    async with SessionLocal() as session:
        task = await session.get(UserTask, task_id)
        if task is None:
            return False

        # Calculate processing time before updating status
        processing_time = 0.0
        if task.processing_started_at:
            end_time = datetime.now()
            processing_time = (end_time - task.processing_started_at).total_seconds()

        # Update task status
        if success:
            # Increment cycle count first
            task.cycles_completed = task.cycles_completed + 1

            # Check if we've reached the maximum cycles
            if task.cycles_completed >= task.max_cycles:
                # Task is complete - no more cycles needed
                task.status = TaskStatus.COMPLETED
                task.processing_completed_at = datetime.now()

                # Check if task has results and send notification
                results = await get_user_task_results(task.id)
                has_results = len(results) > 0

                # Send cycle limit notification asynchronously
                await _notify_cycle_limit_reached(task, has_results)
            else:
                # More cycles needed - return to queue for next iteration
                task.status = TaskStatus.QUEUED
                # Don't set processing_completed_at yet as task is not fully complete

                # Update queue entry to reset processing state
                queue_result = await session.execute(
                    select(TaskQueue).where(TaskQueue.task_id == task.id)
                )
                queue_entry = queue_result.scalar_one_or_none()
                if queue_entry:
                    queue_entry.worker_id = None  # Reset worker assignment
                    queue_entry.started_at = None  # Reset start time for reprocessing
                    queue_entry.updated_at = datetime.now()
        else:
            task.status = TaskStatus.FAILED
            task.processing_completed_at = (
                datetime.now()
            )  # Set completion time even for failures
            task.error_message = error_message

        task.updated_at = datetime.now()

        await session.commit()

        # Update global statistics
        await update_task_statistics(processing_time, success)

        return True


async def create_research_topic_for_user_task(
    user_task: UserTask,
) -> Optional[ResearchTopic]:
    """Create a ResearchTopic from UserTask for agent compatibility.

    This bridges the new UserTask system with the legacy ResearchTopic system
    that the agent pipeline expects.

    :param user_task: UserTask instance
    :returns: ResearchTopic instance or None if user not found
    """
    async with SessionLocal() as session:
        # Get user by internal ID
        user = await session.get(User, user_task.user_id)
        if user is None:
            return None

        # Check if research topic already exists for this task
        # Use full description for exact matching
        existing_result = await session.execute(
            select(ResearchTopic).where(
                and_(
                    ResearchTopic.user_id
                    == user.telegram_id,  # Use telegram_id for legacy compatibility
                    ResearchTopic.target_topic == user_task.description,  # Exact match
                    ResearchTopic.is_active,
                )
            )
        )
        existing_topic = existing_result.scalar_one_or_none()

        if existing_topic:
            return existing_topic

        # Create new research topic
        topic = ResearchTopic(
            user_id=user.telegram_id,  # Use telegram_id for legacy compatibility
            target_topic=user_task.description,
            search_area=user_task.title or user_task.description[:100],
            is_active=True,
        )

        session.add(topic)
        await session.commit()
        await session.refresh(topic)

        return topic


async def link_analysis_to_user_task(
    analysis: PaperAnalysis, user_task: UserTask
) -> None:
    """Link a paper analysis to a user task for proper result tracking.

    Creates a Finding record that connects the analysis to the user's task.

    :param analysis: PaperAnalysis instance
    :param user_task: UserTask instance
    """
    async with SessionLocal() as session:
        # Create finding record
        finding = Finding(
            task_id=user_task.id,
            paper_id=analysis.paper_id,
            relevance=analysis.relevance,
            summary=analysis.summary,
        )

        session.add(finding)
        await session.commit()


async def get_user_task_results(task_id: int) -> List[Tuple[PaperAnalysis, ArxivPaper]]:
    """Get analysis results for a user task.

    :param task_id: UserTask ID
    :returns: List of (PaperAnalysis, ArxivPaper) tuples
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(PaperAnalysis, ArxivPaper)
            .join(Finding, PaperAnalysis.paper_id == Finding.paper_id)
            .join(ArxivPaper, PaperAnalysis.paper_id == ArxivPaper.id)
            .where(Finding.task_id == task_id)
            .order_by(PaperAnalysis.relevance.desc())
        )
        rows = result.all()
        return [(row[0], row[1]) for row in rows]


# Legacy function for compatibility (used in bot/handlers/task.py)
async def create_user_task(user_id: int, description: str) -> UserTask:
    """Create a user task (legacy function for compatibility).

    :param user_id: Telegram user ID (will be converted to internal user ID)
    :param description: Task description
    :returns: UserTask instance
    """
    # Get or create user by telegram_id
    user = await get_or_create_user(telegram_id=user_id)

    # Use the enhanced task creation function
    task, _ = await create_user_task_with_queue(user, description)
    return task


async def _notify_cycle_limit_reached(user_task: UserTask, has_results: bool) -> None:
    """Send notification to user when cycle limit is reached.

    :param user_task: The completed user task
    :param has_results: Whether the task produced any results
    """
    # Get user telegram_id for notification
    async with SessionLocal() as session:
        user = await session.get(User, user_task.user_id)
        if user is None:
            return

        telegram_id = user.telegram_id
        plan_name = "Premium" if user.plan == UserPlan.PREMIUM else "Free"

        if has_results:
            # User has results - congratulate and offer to continue
            message = f"""
🎉 <b>Task #{user_task.id} completed!</b>

✅ <b>Results found for your query:</b>
📝 <i>{user_task.description[:100]}{"..." if len(user_task.description) > 100 else ""}</i>

🔄 <b>Cycles completed:</b> {user_task.cycles_completed}/{user_task.max_cycles} (Plan: {plan_name})

🤖 Hope the results were helpful! 

💡 <b>Want to continue research?</b>
• Create a new task with a refined query
• Or get a Premium subscription for unlimited search cycles

Use /task to create a new task or /status to view results.
            """.strip()
        else:
            # No results found - suggest refinement or premium
            message = f"""
🔄 <b>Task #{user_task.id} completed</b>

📝 <i>{user_task.description[:100]}{"..." if len(user_task.description) > 100 else ""}</i>

🔄 <b>Cycles completed:</b> {user_task.cycles_completed}/{user_task.max_cycles} (Plan: {plan_name})

❌ <b>Unfortunately, no results found for this query.</b>

💡 <b>Recommendations:</b>
• Try reformulating the query more specifically
• Use different keywords
• Or get a Premium subscription for more search cycles

Use /task to create a new task with a refined query.
            """.strip()

        # Create notification task
        data = {"task_type": "cycle_limit_notification", "user_id": telegram_id}
        await create_task(
            task_type="cycle_limit_notification",
            data=data,
            status="completed",
            result=message,
        )
