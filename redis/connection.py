"""
Distributed Redis Client & Connection Pool Factory.
"""

from __future__ import annotations

import logging
import os

import redis.asyncio as aioredis
from config import settings

LOGGER = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis_url() -> str:
    return os.environ.get("REDIS_URL") or settings.redis.url


async def get_redis_client() -> aioredis.Redis:
    """Lazy-initialize singleton Async Redis client."""
    global _redis_client
    if _redis_client is None:
        url = get_redis_url()
        _redis_client = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis.max_connections,
            socket_timeout=settings.redis.socket_timeout,
        )
        LOGGER.info(
            "redis_async_client_initialized",
            extra={"redis_url_redacted": url.split("@")[-1]},
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        LOGGER.info("redis_async_client_closed")
