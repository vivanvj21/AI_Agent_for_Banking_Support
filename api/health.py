"""
FastAPI — readiness and liveness endpoints.

Extends api/main.py with /health/live and /health/ready
endpoints that container orchestrators (Docker, K8s) use to
gate traffic and restart unhealthy pods.

These are imported and registered by api/main.py.
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import validate_startup

_start_time = time.time()
_ready = False  # set True once lifespan startup completes

router = APIRouter(prefix="/health", tags=["health"])


def mark_ready() -> None:
    """Call this at the end of lifespan startup."""
    global _ready
    _ready = True


@router.get("/live", summary="Liveness probe")
def liveness():
    """
    Always returns 200 while the process is alive.
    If this endpoint fails, the container is dead and should be restarted.
    """
    return {"status": "alive", "uptime_seconds": round(time.time() - _start_time, 1)}


@router.get("/ready", summary="Readiness probe")
def readiness():
    """
    Returns 200 when the app has finished startup and is ready to serve traffic.
    Returns 503 during startup or if a critical dependency is unavailable.
    """
    if not _ready:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "ready": False},
        )

    # Quick dependency checks (no LLM call — that's expensive)
    status = validate_startup(require_llm=False, initialize=False)
    if not status.ok:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "ready": False, "reason": status.message},
        )

    return {
        "status": "ready",
        "ready": True,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "details": status.details,
    }
