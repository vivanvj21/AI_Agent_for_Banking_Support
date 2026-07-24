"""
Minimal in-process request metrics for GET /metrics.

Deliberately not wired to Prometheus/CloudWatch/Grafana -- the README is
explicit that this project doesn't ship a fake observability integration
with no real backend behind it (see "What's cut from a 'full' production
version" in README.md). This gives honest, real numbers for the process
that's actually running, which is enough for a demo /metrics endpoint.
Swapping this for a prometheus_client Counter/Histogram later is a
contained change: only this file would need to change.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_start_time = time.perf_counter()
_counts: dict[str, int] = defaultdict(int)
_total_latency_ms: dict[str, float] = defaultdict(float)


def record_request(endpoint: str, elapsed_seconds: float) -> None:
    with _lock:
        _counts[endpoint] += 1
        _total_latency_ms[endpoint] += elapsed_seconds * 1000.0


def snapshot() -> dict:
    with _lock:
        counts = dict(_counts)
        averages = {
            endpoint: round(_total_latency_ms[endpoint] / _counts[endpoint], 2)
            for endpoint in _counts
        }
    return {
        "uptime_seconds": round(time.perf_counter() - _start_time, 2),
        "request_counts": counts,
        "average_latency_ms": averages,
    }
