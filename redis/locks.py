"""
Distributed Lock implementation backed by Redis (SET NX EX algorithm).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from redis.connection import get_redis_client

LOGGER = logging.getLogger(__name__)


class DistributedLockError(Exception):
    """Raised when lock acquisition fails or timed out."""
    pass


class DistributedLock:
    def __init__(self, name: str, timeout: float = 10.0, retry_delay: float = 0.1) -> None:
        self.name = f"lock:{name}"
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.token = uuid.uuid4().hex

    async def acquire(self, wait_timeout: float = 5.0) -> bool:
        client = await get_redis_client()
        start = asyncio.get_event_loop().time()
        ttl_ms = int(self.timeout * 1000)

        while True:
            # Atomic SET key token NX PX ttl_ms
            ok = await client.set(self.name, self.token, nx=True, px=ttl_ms)
            if ok:
                LOGGER.debug("redis_lock_acquired", extra={"lock": self.name, "token": self.token})
                return True
            
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= wait_timeout:
                return False
            
            await asyncio.sleep(self.retry_delay)

    async def release(self) -> bool:
        client = await get_redis_client()
        # Lua script guarantees release only if token matches
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            res = await client.eval(lua_script, 1, self.name, self.token)
            if res:
                LOGGER.debug("redis_lock_released", extra={"lock": self.name})
                return True
        except Exception as exc:
            LOGGER.error("redis_lock_release_failed", extra={"lock": self.name, "error": str(exc)})
        return False


@asynccontextmanager
async def distributed_lock(name: str, timeout: float = 10.0, wait_timeout: float = 5.0) -> AsyncGenerator[None, None]:
    lock = DistributedLock(name=name, timeout=timeout)
    acquired = await lock.acquire(wait_timeout=wait_timeout)
    if not acquired:
        raise DistributedLockError(f"Could not acquire lock '{name}' within {wait_timeout}s")
    try:
        yield
    finally:
        await lock.release()
