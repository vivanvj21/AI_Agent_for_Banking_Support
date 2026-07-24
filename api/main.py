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

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.metrics import snapshot
from api.routes import router
from api.schemas import MetricsResponse
from config import validate_startup
from logging_config import configure_logging

configure_logging()
LOGGER = logging.getLogger(__name__)

app = FastAPI(
    title="Autonomous Bank Assistant API",
    description=(
        "REST interface over the existing LangGraph multi-agent banking "
        "assistant. Wraps the same graph, agents, tools, and memory layer "
        "used by cli.py and app_streamlit.py -- no business logic is "
        "duplicated here."
    ),
    version="1.0.0",
)


@app.on_event("startup")
def on_startup() -> None:
    """
    Same idempotent initialization cli.py/app_streamlit.py already perform
    (SQLite schema + demo data, Chroma FAQ index) via config.validate_startup.
    require_llm=False here on purpose: a missing ANTHROPIC_API_KEY should not
    prevent the process from starting and serving /health and /faq/search --
    it will surface as a 503 from /chat specifically, same as
    MissingAPIKeyError does in cli.py/app_streamlit.py.
    """
    status = validate_startup(require_llm=False, initialize=True)
    if not status.ok:
        LOGGER.error("api_startup_validation_failed", extra={"details": status.details})
    else:
        LOGGER.info("api_startup_validation_ok", extra={"details": status.details})


app.include_router(router)


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(**snapshot())


@app.exception_handler(Exception)
def unhandled_exception_handler(request, exc):  # noqa: ANN001, ARG001
    LOGGER.exception("api_unhandled_exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. See server logs for details."},
    )
