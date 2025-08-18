"""Task management operations."""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from ..connection import SessionLocal
from ..models import User, UserTask, TaskQueue
from ..enums import UserPlan, TaskStatus
from .queue import add_task_to_queue


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
