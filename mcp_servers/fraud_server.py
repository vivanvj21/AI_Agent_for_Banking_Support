"""
NEW FILE — does not modify anything in tools/ or agents/.

MCP server exposing the fraud tools (lock_card, unlock_card,
report_card_lost, report_fraud_transaction, get_flagged_transactions) over
MCP. Wraps tools/fraud_tools.py unchanged — no reimplemented logic here.

Run standalone to test:
    python mcp_servers/fraud_server.py

See mcp_servers/test_fraud_client.py for a client that exercises this
server end-to-end, including the cross-user ownership check.
"""

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from mcp_servers.common import LOGGER, safe_mcp_call
from tools.fraud_tools import (
    get_flagged_transactions as _get_flagged_transactions,
)
from tools.fraud_tools import (
    lock_card as _lock_card,
)
from tools.fraud_tools import (
    report_card_lost as _report_card_lost,
)
from tools.fraud_tools import (
    report_fraud_transaction as _report_fraud_transaction,
)
from tools.fraud_tools import (
    unlock_card as _unlock_card,
)

mcp = FastMCP("bank-fraud-server")

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


def _validate_card_id(card_id: str) -> bool:
    """Validate card_id: same as user_id."""
    return _validate_user_id(card_id)


def _validate_transaction_id(transaction_id: str) -> bool:
    """Validate transaction_id: same as user_id."""
    return _validate_user_id(transaction_id)


def _validate_reason(reason: str) -> bool:
    """Validate reason: optional string, max 200 chars."""
    if reason is None:
        return True
    return isinstance(reason, str) and len(reason) <= 200


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
    card_id = kwargs.get("card_id")
    transaction_id = kwargs.get("transaction_id")
    reason = kwargs.get("reason")

    # Input validation
    if not _validate_user_id(user_id):
        LOGGER.warning(
            "mcp_validation_failed",
            extra={"tool": tool_name, "user_id": user_id, "reason": "invalid_user_id"},
        )
        return {"error": "Invalid request."}

    if tool_name in ["lock_card", "unlock_card", "report_card_lost"]:
        if not _validate_card_id(card_id):
            LOGGER.warning(
                "mcp_validation_failed",
                extra={
                    "tool": tool_name,
                    "user_id": user_id,
                    "card_id": card_id,
                    "reason": "invalid_card_id",
                },
            )
            return {"error": "Invalid request."}

    if tool_name == "report_fraud_transaction":
        if not _validate_transaction_id(transaction_id):
            LOGGER.warning(
                "mcp_validation_failed",
                extra={
                    "tool": tool_name,
                    "user_id": user_id,
                    "transaction_id": transaction_id,
                    "reason": "invalid_transaction_id",
                },
            )
            return {"error": "Invalid request."}
        if not _validate_reason(reason):
            LOGGER.warning(
                "mcp_validation_failed",
                extra={
                    "tool": tool_name,
                    "user_id": user_id,
                    "reason": reason,
                    "validation_error": "invalid_reason",
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
                "card_id": card_id,
                "transaction_id": transaction_id,
                "reason": reason,
                "error": result.get("error"),
            },
        )
    else:
        LOGGER.info(
            "mcp_tool_success",
            extra={
                "tool": tool_name,
                "user_id": user_id,
                "card_id": card_id,
                "transaction_id": transaction_id,
                "reason": reason,
            },
        )

    return result


@mcp.tool()
def lock_card(user_id: str, card_id: str) -> dict:
    """Instantly lock a card belonging to the given user. Reversible."""
    return secure_mcp_call("lock_card", _lock_card, user_id=user_id, card_id=card_id)


@mcp.tool()
def unlock_card(user_id: str, card_id: str) -> dict:
    """Unlock a previously locked card belonging to the given user."""
    return secure_mcp_call(
        "unlock_card", _unlock_card, user_id=user_id, card_id=card_id
    )


@mcp.tool()
def report_card_lost(user_id: str, card_id: str) -> dict:
    """Permanently report a card lost/stolen and trigger replacement. NOT reversible."""
    return secure_mcp_call(
        "report_card_lost", _report_card_lost, user_id=user_id, card_id=card_id
    )


@mcp.tool()
def report_fraud_transaction(
    user_id: str, transaction_id: str, reason: str = ""
) -> dict:
    """Flag a specific transaction as fraudulent for investigation."""
    return secure_mcp_call(
        "report_fraud_transaction",
        _report_fraud_transaction,
        user_id=user_id,
        transaction_id=transaction_id,
        reason=reason,
    )


@mcp.tool()
def get_flagged_transactions(user_id: str) -> dict:
    """List all transactions currently flagged as fraud for the given user."""
    return secure_mcp_call(
        "get_flagged_transactions", _get_flagged_transactions, user_id=user_id
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
