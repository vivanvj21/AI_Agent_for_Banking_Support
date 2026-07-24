"""
Shared FastAPI dependencies.

The important one is `require_verified_user`, which is the REST equivalent
of the graph's verify_gate: it reuses tools/memory.py's session/user linkage
(the SAME table verify_gate_node writes to in graph.py) rather than
inventing a parallel auth mechanism. A session only carries a user_id once
it has gone through /verify or through the graph's verify_gate inside
/chat — there is exactly one place identity gets attached to a session.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException

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
