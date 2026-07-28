"""
FastAPI — readiness and liveness endpoints.

Extends api/main.py with /health/live and /health/ready
endpoints that container orchestrators (Docker, K8s) use to
gate traffic and restart unhealthy pods.

These are imported and registered by api/main.py.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import validate_startup

LOGGER = logging.getLogger(__name__)

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
    Verifies database connectivity, vector store access, and configuration checks
    without exposing sensitive information.
    """
    if not _ready:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "ready": False},
        )

    # 1. Database Check (SQL Connection & Query Execution)
    db_ok = False
    try:
        from db.connection import get_connection
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_ok = True
    except Exception as exc:
        LOGGER.error("health_readiness_db_failed", extra={"error": str(exc)})

    # 2. Chroma Check (Vector Store collections verification)
    chroma_ok = False
    try:
        from tools.faq_search import _get_collection
        collection = _get_collection()
        collection.count()
        chroma_ok = True
    except Exception as exc:
        LOGGER.error("health_readiness_chroma_failed", extra={"error": str(exc)})

    # 3. MCP Platform Check (Discovery state inspection)
    mcp_ok = False
    try:
        from mcp_platform.manager import get_mcp_manager
        mcp_mgr = get_mcp_manager()
        mcp_ok = mcp_mgr.is_ready
    except Exception as exc:
        LOGGER.error("health_readiness_mcp_failed", extra={"error": str(exc)})

    # 4. LLM Configuration Check (Verifies API configuration status)
    llm_ok = False
    try:
        from config import require_llm_config
        require_llm_config()
        llm_ok = True
    except Exception as exc:
        LOGGER.error("health_readiness_llm_config_failed", extra={"error": str(exc)})

    ready = db_ok and chroma_ok and mcp_ok and llm_ok

    status_code = 200 if ready else 503
    status_text = "ready" if ready else "degraded"

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_text,
            "ready": ready,
            "uptime_seconds": round(time.time() - _start_time, 1),
            "checks": {
                "database": "ok" if db_ok else "failed",
                "vector_store": "ok" if chroma_ok else "failed",
                "mcp_platform": "ok" if mcp_ok else "failed",
                "configuration": "ok" if llm_ok else "failed",
            }
        }
    )
