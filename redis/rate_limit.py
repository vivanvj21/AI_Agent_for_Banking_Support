"""
Cluster-wide Sliding Window Rate Limiter using Redis Lua script.
"""

from __future__ import annotations

import logging
import time
from typing import Tuple

from redis.connection import get_redis_client

LOGGER = logging.getLogger(__name__)

# Atomic sliding window rate limiter Lua script
_LUA_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

local clear_before = now - window
redis.call("ZREMRANGEBYSCORE", key, 0, clear_before)

local current_requests = redis.call("ZCARD", key)
if current_requests < limit then
    redis.call("ZADD", key, now, now)
    redis.call("EXPIRE", key, window + 1)
    return {1, limit - current_requests - 1, 0}
else
    local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
    local retry_after = 0
    if #oldest > 0 then
        retry_after = math.ceil((tonumber(oldest[2]) + window) - now)
    end
    if retry_after < 1 then retry_after = 1 end
    return {0, 0, retry_after}
end
"""


class RedisRateLimiter:
    def __init__(self, key_prefix: str = "rate:") -> None:
        self.prefix = key_prefix
        self._script = None

    async def is_allowed(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
    ) -> Tuple[bool, int, int]:
        """
        Check rate limit.
        Returns: (allowed: bool, remaining: int, retry_after_seconds: int)
        """
        try:
            client = await get_redis_client()
            key = f"{self.prefix}{identifier}"
            now = time.time()
            
            res = await client.eval(_LUA_RATE_LIMIT_SCRIPT, 1, key, now, window_seconds, limit)
            allowed = bool(res[0])
            remaining = int(res[1])
            retry_after = int(res[2])
            return allowed, remaining, retry_after
        except Exception as exc:
            LOGGER.error("redis_rate_limit_eval_failed", extra={"identifier": identifier, "error": str(exc)})
            # Fail-open safety policy under Redis failure
            return True, limit, 0


redis_rate_limiter = RedisRateLimiter()
