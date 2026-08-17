"""
Enterprise PostgreSQL & SQLAlchemy Async Connection Pool Factory.

Provides robust connection handling, connection pooling, deadlock retry helpers,
and seamless fallback / configuration loading via DATABASE_URL or settings proxy.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


# Primary Database URL resolution
def get_database_url() -> str:
    """Resolve the PostgreSQL database URL, defaulting to asyncpg driver."""
    url = os.environ.get("DATABASE_URL") or settings.database.url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith(
        "postgresql+asyncpg://"
    ):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    """Lazy-initialize and return the singleton AsyncEngine with enterprise pool settings."""
    global _engine
    if _engine is None:
        db_url = get_database_url()
        is_sqlite = "sqlite" in db_url

        connect_args = {}
        if is_sqlite:
            connect_args["check_same_thread"] = False
            _engine = create_async_engine(
                db_url,
                connect_args=connect_args,
                echo=settings.logging.verbose,
            )
        else:
            _engine = create_async_engine(
                db_url,
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.max_overflow,
                pool_timeout=settings.database.pool_timeout,
                pool_recycle=settings.database.pool_recycle,
                pool_pre_ping=True,
                echo=settings.logging.verbose,
            )
        LOGGER.info(
            "async_db_engine_initialized",
            extra={"db_url_redacted": db_url.split("@")[-1]},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy-initialize and return the singleton async sessionmaker."""
    global _sessionmaker
    if _sessionmaker is None:
        engine = get_async_engine()
        _sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Transactional async session context manager with automatic rollback on exception."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception as exc:
        await session.rollback()
        LOGGER.error("async_db_session_rollback", extra={"error": str(exc)})
        raise
    finally:
        await session.close()


async def execute_with_retry(
    async_fn: Callable[..., asyncio.Future[T] | AsyncGenerator[T, None] | T],
    max_retries: int = 3,
    initial_delay: float = 0.1,
    *args,
    **kwargs,
) -> T:
    """Execute a database operation with exponential backoff for deadlock/transient recovery."""
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            res = async_fn(*args, **kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res
        except (OperationalError, DBAPIError) as exc:
            is_deadlock = (
                "deadlock" in str(exc).lower() or "lock timeout" in str(exc).lower()
            )
            if attempt == max_retries or not is_deadlock:
                LOGGER.error(
                    "db_retry_exhausted_or_fatal",
                    extra={"attempt": attempt, "error": str(exc)},
                )
                raise
            LOGGER.warning(
                "db_transient_error_retrying",
                extra={"attempt": attempt, "delay": delay, "error": str(exc)},
            )
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError("Unexpected end of retry loop")
