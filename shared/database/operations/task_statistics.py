"""Task statistics operations."""

from datetime import datetime

from sqlalchemy import select, func

from ..connection import SessionLocal
from ..models import TaskStatistics, TaskQueue


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
