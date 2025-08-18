"""Rate limiting operations."""

from datetime import datetime
from typing import Tuple

from sqlalchemy import select, and_

from ..connection import SessionLocal
from ..models import RateLimitRecord


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
