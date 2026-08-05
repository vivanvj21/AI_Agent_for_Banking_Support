"""
Shared FastAPI dependencies.

The important one is `require_verified_user`, which is the REST equivalent
of the graph's verify_gate: it reuses tools/memory.py's session/user linkage
(the SAME table verify_gate_node writes to in graph.py) rather than
inventing a parallel auth mechanism. A session only carries a user_id once
it has gone through /verify or through the graph's verify_gate inside
/chat — there is exactly one place identity gets attached to a session.
"""

from functools import lru_cache
import secrets

from fastapi import HTTPException, Request, status

from config import settings
from graph import build_graph
from tools import memory


@lru_cache(maxsize=1)
def get_graph():
    """Build the LangGraph app once per process and reuse it.

    build_graph() itself does no I/O beyond wiring nodes/edges, so caching
    is safe and avoids recompiling the graph on every request.
    """
    return build_graph()


def require_verified_user(session_id: str) -> str:
    """
    Resolve a session_id to a verified user_id, or raise 401/404.

    This mirrors route_after_verify in graph.py: an unverified session must
    not reach account/fraud tools. Here that's enforced by requiring
    tools.memory.get_session_user(session_id) to already be set, which only
    happens after /verify or the graph's verify_gate has succeeded for this
    session_id.
    """
    if not memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id}")

    user_id = memory.get_session_user(session_id)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail=(
                "This session has not completed identity verification yet. "
                "Call POST /verify with this session_id first."
            ),
        )
    return user_id


EXEMPT_PATHS = {
    "/health",
    "/health/live",
    "/health/ready",
    "/metrics",
    "/auth/login",
    "/auth/refresh",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def verify_perimeter_api_key(request: Request) -> None:
    """
    Perimeter Security Control (Phase 12).

    Validates HTTP X-API-Key header against settings.security.api_key using
    constant-time comparison (secrets.compare_digest). Executes BEFORE rate limiting
    to prevent unauthenticated quota exhaustion.

    Exempt paths: /health, /health/live, /health/ready, /docs, /redoc, /openapi.json.
    """
    path = request.url.path
    if path in EXEMPT_PATHS:
        return

    sec_cfg = settings.security
    if not sec_cfg.require_api_key:
        return

    configured_key = sec_cfg.api_key.get_secret_value()
    if not configured_key:
        return

    header_name = sec_cfg.api_key_header_name
    provided_key = request.headers.get(header_name) or request.headers.get(header_name.lower())

    if not provided_key or not secrets.compare_digest(provided_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "ApiKey"},
        )
