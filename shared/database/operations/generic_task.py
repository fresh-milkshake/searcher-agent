"""Generic task operations."""

import json
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import select, and_

from ..connection import SessionLocal
from ..models import Task


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
