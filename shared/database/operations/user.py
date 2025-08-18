"""User management operations."""

from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select, func, and_

from ..connection import SessionLocal
from ..models import User, UserTask
from ..enums import UserPlan, TaskStatus


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
