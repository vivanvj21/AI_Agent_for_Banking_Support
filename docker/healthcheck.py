"""
Docker HEALTHCHECK probe helper.

Detects whether the container is running the Streamlit UI or the FastAPI REST API
and queries the appropriate health endpoint. Returns exit code 0 if healthy, 1 otherwise.
"""

from __future__ import annotations

import os
import sys
import urllib.request


def check_health() -> bool:
    try:
        from config import settings
        port_api = settings.deployment.port_api
        port_streamlit = settings.deployment.port_streamlit
    except Exception:
        port_api = int(os.environ.get("PORT_API", "8000"))
        port_streamlit = int(os.environ.get("PORT_STREAMLIT", "8501"))

    # 1. Try checking the FastAPI API readiness probe
    try:
        urllib.request.urlopen(f"http://localhost:{port_api}/health/live", timeout=2)
        return True
    except Exception:
        pass

    # 2. Try checking the Streamlit UI core health endpoint
    try:
        # Streamlit exposes a core health status check at /_stcore/health
        urllib.request.urlopen(f"http://localhost:{port_streamlit}/_stcore/health", timeout=2)
        return True
    except Exception:
        pass

    return False


if __name__ == "__main__":
    if check_health():
        sys.exit(0)
    sys.exit(1)
