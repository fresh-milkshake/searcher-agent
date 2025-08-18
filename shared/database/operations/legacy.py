"""Legacy operations for compatibility."""

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import select, and_

from ..connection import SessionLocal
from ..models import UserSettings, ResearchTopic


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
