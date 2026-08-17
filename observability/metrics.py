"""
Prometheus Metrics Collector & Instrumentation for FastAPI & System Monitoring.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain"

    class _DummyMetric:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

    Counter = Gauge = Histogram = _DummyMetric

    def generate_latest():
        return b""


# HTTP Request Metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

IN_FLIGHT_REQUESTS = Gauge(
    "http_in_flight_requests",
    "Number of in-flight HTTP requests",
    ["endpoint"],
)

# Business & System Metrics
ACTIVE_SESSIONS = Gauge(
    "banking_active_sessions_total",
    "Total active user conversation sessions",
)

FAILED_AUTH_ATTEMPTS = Counter(
    "security_failed_auth_attempts_total",
    "Total failed authentication / identity verification attempts",
    ["user_id"],
)

CARD_LOCK_EVENTS = Counter(
    "security_card_lock_events_total",
    "Total card locking events executed",
    ["status"],
)

FRAUD_REPORTED_EVENTS = Counter(
    "security_fraud_reported_events_total",
    "Total fraud report events submitted",
)

LLM_TOKEN_USAGE = Counter(
    "llm_token_usage_total",
    "Total LLM tokens consumed",
    ["model", "type"],  # type: prompt / completion
)


async def prometheus_metrics_middleware(
    request: Request, call_next: Callable
) -> Response:
    """FastAPI Middleware collecting HTTP request metrics."""
    endpoint = request.url.path
    method = request.method

    IN_FLIGHT_REQUESTS.labels(endpoint=endpoint).inc()
    start_time = time.perf_counter()

    try:
        response: Response = await call_next(request)
        status_code = str(response.status_code)
        REQUEST_COUNT.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()
        return response
    finally:
        latency = time.perf_counter() - start_time
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)
        IN_FLIGHT_REQUESTS.labels(endpoint=endpoint).dec()


def metrics_response() -> Response:
    """Return raw Prometheus metrics response for GET /metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
