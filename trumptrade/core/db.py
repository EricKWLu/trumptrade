"""Async database engine and session factory for TrumpTrade.

All phases import get_db for FastAPI dependency injection and
AsyncSessionLocal for background task sessions.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trumptrade.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.db_url,  # "sqlite+aiosqlite:///./trumptrade.db"
    echo=_settings.debug,
    future=True,
)

# expire_on_commit=False is MANDATORY for async sessions.
# With the default True, accessing attributes after commit triggers a lazy
# SELECT, which raises MissingGreenlet in an async context.
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields one session per request.

    Usage in route handlers:
        async def my_route(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Model))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
