"""
NEW FILE — does not modify anything in tools/ or agents/.

MCP server exposing the account tools (get_balance, get_transaction_history)
over the Model Context Protocol, using the official `mcp` Python SDK's
FastMCP helper.

This wraps the SAME underlying functions already in tools/account_tools.py —
it does not reimplement the SQL logic. The point of this file is purely to
demonstrate the MCP integration pattern: any MCP-compatible client (Claude
Desktop, another agent, a different LangGraph app) could now call these
tools without needing to import your Python package directly.

Run standalone to test:
    python mcp_servers/account_server.py

This starts the server on stdio and blocks, waiting for a client to connect
(see mcp_servers/test_client.py for a client that connects to it and calls
a tool, all inside this same conversation, no other setup needed).
"""

import sys
import time
from pathlib import Path
from typing import Any

# Make the existing tools/ package importable from this new location
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from mcp_servers.common import LOGGER, safe_mcp_call
from tools.account_tools import get_balance as _get_balance
from tools.account_tools import get_transaction_history as _get_transaction_history

mcp = FastMCP("bank-account-server")

# Simple in-memory rate limiter: fixed window counter
# Structure: { (user_id, tool_name): [timestamp1, timestamp2, ...] }
_REQUEST_HISTORY: dict[tuple[str, str], list[float]] = {}
_RATE_LIMIT_WINDOW_SECONDS = 60  # 1 minute
_RATE_LIMIT_MAX_REQUESTS = 10  # max requests per window


def _validate_user_id(user_id: str) -> bool:
    """Validate user_id: alphanumeric, underscore, hyphen, max 32 chars."""
    if not user_id or not isinstance(user_id, str):
        return False
    if len(user_id) > 32:
        return False
    # Allow alphanumeric, underscore, hyphen
    return all(c.isalnum() or c in ("_", "-") for c in user_id)


def _validate_account_id(account_id: str | None) -> bool:
    """Validate account_id: same as user_id, or None."""
    if account_id is None:
        return True
    return _validate_user_id(account_id)


def _validate_limit(limit: int) -> bool:
    """Validate limit: integer between 1 and 100."""
    return isinstance(limit, int) and 1 <= limit <= 100


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
    user_id = kwargs.get("user_id")
    account_id = kwargs.get("account_id")
    limit = kwargs.get("limit")

    # Input validation
    if not _validate_user_id(user_id):
        LOGGER.warning(
            "mcp_validation_failed",
            extra={"tool": tool_name, "user_id": user_id, "reason": "invalid_user_id"},
        )
        return {"error": "Invalid request."}

    if not _validate_account_id(account_id):
        LOGGER.warning(
            "mcp_validation_failed",
            extra={
                "tool": tool_name,
                "user_id": user_id,
                "account_id": account_id,
                "reason": "invalid_account_id",
            },
        )
        return {"error": "Invalid request."}

    if limit is not None and not _validate_limit(limit):
        LOGGER.warning(
            "mcp_validation_failed",
            extra={
                "tool": tool_name,
                "user_id": user_id,
                "limit": limit,
                "reason": "invalid_limit",
            },
        )
        return {"error": "Invalid request."}

    # Rate limiting
    if _is_rate_limited(user_id, tool_name):
        LOGGER.warning(
            "mcp_rate_limit_exceeded", extra={"tool": tool_name, "user_id": user_id}
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
                "account_id": account_id,
                "limit": limit,
                "error": result.get("error"),
            },
        )
    else:
        LOGGER.info(
            "mcp_tool_success",
            extra={
                "tool": tool_name,
                "user_id": user_id,
                "account_id": account_id,
                "limit": limit,
            },
        )

    return result


@mcp.tool()
def get_balance(user_id: str, account_id: str | None = None) -> dict:
    """
    Get balance for a specific account, or all accounts for a user if
    account_id is omitted. Wraps tools.account_tools.get_balance unchanged.
    """
    return secure_mcp_call(
        "get_balance", _get_balance, user_id=user_id, account_id=account_id
    )


@mcp.tool()
def get_transaction_history(
    user_id: str, account_id: str | None = None, limit: int = 10
) -> dict:
    """
    Get recent transactions for a user, optionally scoped to one account.
    Wraps tools.account_tools.get_transaction_history unchanged.
    """
    return secure_mcp_call(
        "get_transaction_history",
        _get_transaction_history,
        user_id=user_id,
        account_id=account_id,
        limit=limit,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
