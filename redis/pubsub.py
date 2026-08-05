"""
Pub/Sub Event Bus backed by Redis for real-time notifications and audit triggers.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict

from redis.connection import get_redis_client

LOGGER = logging.getLogger(__name__)


class EventBus:
    def __init__(self, channel_prefix: str = "events:") -> None:
        self.prefix = channel_prefix

    def _channel(self, topic: str) -> str:
        return f"{self.prefix}{topic}"

    async def publish(self, topic: str, payload: Dict[str, Any]) -> int:
        try:
            client = await get_redis_client()
            message = json.dumps(payload)
            subscribers = await client.publish(self._channel(topic), message)
            LOGGER.debug("redis_event_published", extra={"topic": topic, "subscribers": subscribers})
            return subscribers
        except Exception as exc:
            LOGGER.error("redis_event_publish_failed", extra={"topic": topic, "error": str(exc)})
            return 0

    async def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        client = await get_redis_client()
        pubsub = client.pubsub()
        channel = self._channel(topic)
        await pubsub.subscribe(channel)
        LOGGER.info("redis_event_subscribed", extra={"channel": channel})

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    res = handler(data)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as exc:
                    LOGGER.error("redis_event_handler_failed", extra={"topic": topic, "error": str(exc)})


event_bus = EventBus()
