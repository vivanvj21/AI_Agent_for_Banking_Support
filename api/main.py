"""
FastAPI entrypoint for the Autonomous Bank Assistant.

This is an ADDITIONAL interface alongside cli.py and app_streamlit.py -- it
does not replace either. All three call the exact same graph.py /
tools/*.py code underneath; nothing in agents/, tools/, or graph.py was
changed to support this file.

Run (dev):
    uvicorn api.main:app --reload --port 8000

Run (same idempotent startup init the CLI/Streamlit apps already do, but
failing fast instead of printing a friendly CLI message, since this is a
server process):
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Docs are auto-served at /docs (Swagger) and /redoc once running.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.health import mark_ready
from api.health import router as health_router
from api.mcp_routes import router as mcp_router
from api.metrics import snapshot
from api.routes import router
from api.schemas import MetricsResponse
from config import get_allowed_origins, validate_startup
from logging_config import configure_logging
from mcp_platform.manager import get_mcp_manager
from tools.memory import cleanup_old_sessions

configure_logging()
LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: run startup logic, yield, then run shutdown logic."""
    # --- Startup ---
    status = validate_startup(require_llm=False, initialize=True)
    if not status.ok:
        LOGGER.error("api_startup_validation_failed", extra={"details": status.details})
    else:
        LOGGER.info("api_startup_validation_ok", extra={"details": status.details})

    # Remove sessions inactive for longer than the default retention window.
    try:
        cleanup_result = cleanup_old_sessions()
        LOGGER.info("api_startup_session_cleanup", extra=cleanup_result)
    except Exception:
        LOGGER.exception("api_startup_session_cleanup_failed")

    # Phase 6: ensure memory tables exist and run expiration cleanup
    try:
        from memory.manager import get_memory_manager

        mgr = get_memory_manager()
        mgr.ensure_ready()
        expired = mgr.expire_old_memories()
        LOGGER.info("api_startup_memory_ready", extra=expired)
    except Exception:
        LOGGER.exception("api_startup_memory_init_failed")

    # Phase 9: Initialize MCP platform and run tool discovery
    try:
        mcp_mgr = get_mcp_manager()
        discovery_results = mcp_mgr.initialize(skip_discovery=False)
        LOGGER.info(
            "api_startup_mcp_ready",
            extra={
                "snapshot": mcp_mgr.get_registry_snapshot(),
                "discovery": discovery_results,
            },
        )
    except Exception:
        LOGGER.exception("api_startup_mcp_init_failed")

    try:
        from config import settings
        from api.rate_limiter import rate_limit_chat, rate_limit_verify, rate_limit_default
        LOGGER.info(
            "api_startup_config",
            extra={
                "environment": settings.app.env,
                "fingerprint": settings.get_fingerprint(),
                "allowed_origins": get_allowed_origins(),
                "report": settings.get_startup_report(),
                "rate_limits": {
                    "chat": f"{rate_limit_chat.times} requests per {rate_limit_chat.seconds}s",
                    "verify": f"{rate_limit_verify.times} requests per {rate_limit_verify.seconds}s",
                    "default": f"{rate_limit_default.times} requests per {rate_limit_default.seconds}s",
                },
            },
        )
    except Exception:
        LOGGER.warning("api_startup_config_logging_failed", exc_info=True)

    # Signal readiness — /health/ready now returns 200
    mark_ready()
    LOGGER.info("api_ready")

    yield  # Application is running.

    # --- Shutdown ---
    LOGGER.info("api_shutdown")


app = FastAPI(
    title="Autonomous Bank Assistant API",
    description=(
        "REST interface over the existing LangGraph multi-agent banking "
        "assistant. Wraps the same graph, agents, tools, and memory layer "
        "used by cli.py and app_streamlit.py — no business logic is "
        "duplicated here."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration: load whitelisted origins from the centralized config module.
# To support session cookies and authorization headers securely in bank systems,
# allow_credentials is set to True. Under the W3C spec, this constraint prevents
# the use of wildcard '*' origins, which is validated during config loading.
from api.auth import router as auth_router
from observability.metrics import prometheus_metrics_middleware, metrics_response

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.middleware("http")(prometheus_metrics_middleware)

app.include_router(router)
app.include_router(auth_router)
app.include_router(health_router)  # /health/live and /health/ready
app.include_router(mcp_router)  # /mcp/status, /mcp/tools, /mcp/call


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "Autonomous Bank Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "ready": "/health/ready",
    }


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(**snapshot())


@app.exception_handler(Exception)
def unhandled_exception_handler(request, exc):
    LOGGER.exception("api_unhandled_exception")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. See server logs for details."
        },
    )
