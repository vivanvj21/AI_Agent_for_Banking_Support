"""
Distributed Session Manager backed by Redis.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from redis.connection import get_redis_client

LOGGER = logging.getLogger(__name__)


class RedisSessionManager:
    def __init__(self, prefix: str = "session:", default_ttl: int = 86400) -> None:
        self.prefix = prefix
        self.default_ttl = default_ttl

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            client = await get_redis_client()
            raw = await client.get(self._key(session_id))
            if raw:
                # Refresh TTL on access (sliding window)
                await client.expire(self._key(session_id), self.default_ttl)
                return json.loads(raw)
        except Exception as exc:
            LOGGER.error("redis_session_get_failed", extra={"session_id": session_id, "error": str(exc)})
        return None

    async def save_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        try:
            client = await get_redis_client()
            expiry = ttl or self.default_ttl
            payload = json.dumps(data)
            await client.set(self._key(session_id), payload, ex=expiry)
            return True
        except Exception as exc:
            LOGGER.error("redis_session_save_failed", extra={"session_id": session_id, "error": str(exc)})
            return False

    async def delete_session(self, session_id: str) -> bool:
        try:
            client = await get_redis_client()
            await client.delete(self._key(session_id))
            return True
        except Exception as exc:
            LOGGER.error("redis_session_delete_failed", extra={"session_id": session_id, "error": str(exc)})
            return False


session_manager = RedisSessionManager()
