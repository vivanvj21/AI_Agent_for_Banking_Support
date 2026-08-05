"""
FastAPI dependency and session management for Async SQLAlchemy Sessions.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_async_session, get_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI request dependency yielding an AsyncSession."""
    async with get_async_session() as session:
        yield session
