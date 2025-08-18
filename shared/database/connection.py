"""Database connection management."""

import os
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base

DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Initialize database and create all tables including new user management and queue tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize default task statistics if none exist
    from .operations import get_or_create_task_statistics

    await get_or_create_task_statistics()


def ensure_connection() -> None:
    """Async SQLAlchemy manages connections via the session. No-op retained for compatibility."""
    return None
