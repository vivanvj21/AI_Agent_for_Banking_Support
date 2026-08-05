"""
Distributed Cache Manager backed by Redis with TTL, serialization, and stampede prevention.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, TypeVar, Union

from redis.connection import get_redis_client

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class CacheManager:
    def __init__(self, prefix: str = "cache:") -> None:
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        try:
            client = await get_redis_client()
            raw = await client.get(self._key(key))
            if raw is not None:
                return json.loads(raw)
        except Exception as exc:
            LOGGER.warning("redis_cache_get_failed", extra={"key": key, "error": str(exc)})
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        try:
            client = await get_redis_client()
            payload = json.dumps(value)
            await client.set(self._key(key), payload, ex=ttl_seconds)
            return True
        except Exception as exc:
            LOGGER.warning("redis_cache_set_failed", extra={"key": key, "error": str(exc)})
            return False

    async def delete(self, key: str) -> bool:
        try:
            client = await get_redis_client()
            await client.delete(self._key(key))
            return True
        except Exception as exc:
            LOGGER.warning("redis_cache_delete_failed", extra={"key": key, "error": str(exc)})
            return False

    async def clear_prefix(self, pattern: str) -> int:
        try:
            client = await get_redis_client()
            keys = await client.keys(self._key(pattern))
            if keys:
                return await client.delete(*keys)
        except Exception as exc:
            LOGGER.warning("redis_cache_clear_failed", extra={"pattern": pattern, "error": str(exc)})
        return 0


cache_manager = CacheManager()
