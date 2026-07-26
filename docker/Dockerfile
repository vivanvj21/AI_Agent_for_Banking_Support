# ─────────────────────────────────────────────────────────────
# Autonomous Bank Assistant — Production Dockerfile
# Multi-stage build: builder installs deps, runtime is lean.
# ─────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ──────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps needed only at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT_STREAMLIT=8501 \
    PORT_API=8000

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create runtime directories that must exist at startup
# (volumes will be mounted over these in Docker Compose)
RUN mkdir -p \
    db \
    logs \
    knowledge_base/chroma_store \
    knowledge_base/chroma_memory \
    knowledge_base/faq_docs \
    evaluation_reports

# Non-root user for production security
RUN addgroup --system bankapp && adduser --system --ingroup bankapp bankapp \
    && chown -R bankapp:bankapp /app
USER bankapp

# Both ports exposed; runtime CMD selects which service to run
EXPOSE 8501 8000

# Health check via FastAPI /health (or override in compose)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT_API}/health')" \
    || exit 1

# Default: Streamlit UI.
# Override at runtime:
#   docker run ... bank-assistant python -m uvicorn api.main:app --host 0.0.0.0
#   docker run ... bank-assistant python cli.py
CMD ["streamlit", "run", "app_streamlit.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
