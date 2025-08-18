"""Queue management operations."""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func

from ..connection import SessionLocal
from ..models import User, UserTask, TaskQueue
from ..enums import UserPlan, TaskStatus
from .task_statistics import get_or_create_task_statistics


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
