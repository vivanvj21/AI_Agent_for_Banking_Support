"""
NEW FILE — does not modify anything in tools/ or agents/.

MCP server exposing the FAQ/policy vector search tool over MCP. Wraps
tools/faq_search.py unchanged — same Chroma-backed retrieval, same
pluggable embedding provider (see tools/embeddings.py).

Run standalone to test:
    python mcp_servers/faq_server.py

See mcp_servers/test_faq_client.py for a client that exercises this
server end-to-end.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from mcp_servers.common import LOGGER, safe_mcp_call
from tools.faq_search import search_faq as _search_faq

mcp = FastMCP("bank-faq-server")

# Simple in-memory rate limiter: fixed window counter
# Structure: { (user_id, tool_name): [timestamp1, timestamp2, ...] }
_REQUEST_HISTORY: Dict[Tuple[str, str], List[float]] = {}
_RATE_LIMIT_WINDOW_SECONDS = 60  # 1 minute
_RATE_LIMIT_MAX_REQUESTS = 10    # max requests per window


def _validate_user_id(user_id: str) -> bool:
    """Validate user_id: alphanumeric, underscore, hyphen, max 32 chars."""
    if not user_id or not isinstance(user_id, str):
        return False
    if len(user_id) > 32:
        return False
    # Allow alphanumeric, underscore, hyphen
    return all(c.isalnum() or c in ('_', '-') for c in user_id)


def _validate_source(source: str | None) -> bool:
    """Validate source: same as user_id, or None."""
    if source is None:
        return True
    return _validate_user_id(source)


def _validate_k(k: int) -> bool:
    """Validate k: integer between 1 and 10."""
    return isinstance(k, int) and 1 <= k <= 10


def _is_rate_limited(user_id: str, tool_name: str) -> bool:
    """Check if the user has exceeded the rate limit for the given tool."""
    key = (user_id, tool_name)
    now = time.time()
    # Initialize or clean old requests
    if key not in _REQUEST_HISTORY:
        _REQUEST_HISTORY[key] = []
    # Remove requests older than the window
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    window_requests = [ts for ts in _REQUEST_HISTORY[key] if ts >= window_start]
    _REQUEST_HISTORY[key] = window_requests
    # Check if we're at the limit
    if len(window_requests) >= _RATE_LIMIT_MAX_REQUESTS:
        return True
    # Add current request timestamp
    _REQUEST_HISTORY[key].append(now)
    return False


def secure_mcp_call(tool_name: str, func: callable, **kwargs: Any) -> dict:
    """
    Wrapper around safe_mcp_call that adds input validation, rate limiting,
    and security logging.
    """
    # Extract parameters we care about for validation and logging
    user_id = kwargs.get('user_id')
    source = kwargs.get('source')
    k = kwargs.get('k')

    # Input validation
    if not _validate_user_id(user_id):
        LOGGER.warning(
            "mcp_validation_failed",
            extra={"tool": tool_name, "user_id": user_id, "reason": "invalid_user_id"}
        )
        return {"error": "Invalid request."}

    if not _validate_source(source):
        LOGGER.warning(
            "mcp_validation_failed",
            extra={"tool": tool_name, "user_id": user_id, "source": source, "reason": "invalid_source"}
        )
        return {"error": "Invalid request."}

    if k is not None and not _validate_k(k):
        LOGGER.warning(
            "mcp_validation_failed",
            extra={"tool": tool_name, "user_id": user_id, "k": k, "reason": "invalid_k"}
        )
        return {"error": "Invalid request."}

    # Rate limiting
    if _is_rate_limited(user_id, tool_name):
        LOGGER.warning(
            "mcp_rate_limit_exceeded",
            extra={"tool": tool_name, "user_id": user_id}
        )
        return {"error": "Too many requests. Please try again later."}

    # Proceed with the original safe_mcp_call
    result = safe_mcp_call(tool_name, func, **kwargs)

    # Log success or failure based on result
    if "error" in result:
        LOGGER.warning(
            "mcp_tool_failed",
            extra={
                "tool": tool_name,
                "user_id": user_id,
                "source": source,
                "k": k,
                "error": result.get("error")
            }
        )
    else:
        LOGGER.info(
            "mcp_tool_success",
            extra={
                "tool": tool_name,
                "user_id": user_id,
                "source": source,
                "k": k
            }
        )

    return result


@mcp.tool()
def search_faq(query: str, k: int = 3, source: str | None = None) -> dict:
    """
    Semantic search over the bank's FAQ/policy knowledge base.
    Returns top-k chunks with their source doc name.
    """
    return secure_mcp_call(
        "search_faq", _search_faq, query=query, k=k, source=source
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")