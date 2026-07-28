"""
API rate limiting dependencies.

Provides a thread-safe, in-memory sliding window rate limiter implementation.
Enforces limits based on client IP addresses (resolving X-Forwarded-For when
deployed behind a reverse proxy or load balancer).

MVP Scope & Limitations:
------------------------
This rate limiter is designed for a single-instance uvicorn deployment (appropriate
for the current project lifecycle phase). Because the state is stored in-memory
using python collections:
1. Rate limit state is NOT shared across multiple horizontally scaled instances.
2. Restarting the FastAPI process resets all request history counters.
For multi-instance, production-grade distributed architectures, these counters should
be backed by a centralized cache layer (such as Redis or Memcached).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status

from config import get_rate_limit

LOGGER = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe, in-memory sliding window rate limiter for FastAPI dependencies.

    Attributes:
        env_var: The name of the environment variable containing overrides.
        default_times: Number of requests allowed within the window.
        default_seconds: Duration of the sliding window in seconds.
    """

    def __init__(self, env_var: str, default_times: int, default_seconds: int) -> None:
        self.env_var = env_var
        # Resolve limit parameters from centralized configuration
        self.times, self.seconds = get_rate_limit(env_var, default_times, default_seconds)
        self.history: dict[str, deque[float]] = {}
        self._lock = Lock()  # Prevents race conditions and state corruption across ASGI threads

    def __call__(self, request: Request) -> None:
        """Evaluate the rate limit for the incoming request's client IP.

        Args:
            request: The incoming FastAPI HTTP request.

        Raises:
            HTTPException: 429 Too Many Requests if the limit is exceeded.
        """
        # Resolve client IP. If behind a proxy (Nginx, ALB), read x-forwarded-for first.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Capture the client-facing IP (first element of the proxy chain)
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        now = time.time()
        with self._lock:  # Critical section: access and modify self.history dictionary
            timestamps = self.history.setdefault(client_ip, deque())

            # Evict timestamps older than the sliding window limit
            while timestamps and timestamps[0] < now - self.seconds:
                timestamps.popleft()

            # Check if threshold has been exceeded
            if len(timestamps) >= self.times:
                # Calculate the exact retry duration based on the oldest window item
                retry_after = int(self.seconds - (now - timestamps[0]))
                retry_after = max(1, retry_after)
                LOGGER.warning(
                    "rate_limit_exceeded",
                    extra={
                        "client_ip": client_ip,
                        "limit": self.times,
                        "window": self.seconds,
                        "retry_after": retry_after,
                        "endpoint": request.url.path,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

            # Record this request timestamp
            timestamps.append(now)


# Standardized Category Dependencies
# Limits default to:
#  - Chat: 10 requests / 60 seconds (protects costly LLM tokens)
#  - Verify: 5 requests / 60 seconds (protects authentication brute-force)
#  - Default: 15 requests / 60 seconds (general endpoints)
rate_limit_chat = RateLimiter("RATE_LIMIT_CHAT", default_times=10, default_seconds=60)
rate_limit_verify = RateLimiter("RATE_LIMIT_VERIFY", default_times=5, default_seconds=60)
rate_limit_default = RateLimiter("RATE_LIMIT_DEFAULT", default_times=15, default_seconds=60)
