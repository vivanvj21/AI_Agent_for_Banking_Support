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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from mcp_servers.common import safe_mcp_call
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


@mcp.tool()
def lock_card(user_id: str, card_id: str) -> dict:
    """Instantly lock a card belonging to the given user. Reversible."""
    return safe_mcp_call("lock_card", _lock_card, user_id=user_id, card_id=card_id)


@mcp.tool()
def unlock_card(user_id: str, card_id: str) -> dict:
    """Unlock a previously locked card belonging to the given user."""
    return safe_mcp_call("unlock_card", _unlock_card, user_id=user_id, card_id=card_id)


@mcp.tool()
def report_card_lost(user_id: str, card_id: str) -> dict:
    """Permanently report a card lost/stolen and trigger replacement. NOT reversible."""
    return safe_mcp_call(
        "report_card_lost", _report_card_lost, user_id=user_id, card_id=card_id
    )


@mcp.tool()
def report_fraud_transaction(
    user_id: str, transaction_id: str, reason: str = ""
) -> dict:
    """Flag a specific transaction as fraudulent for investigation."""
    return safe_mcp_call(
        "report_fraud_transaction",
        _report_fraud_transaction,
        user_id=user_id,
        transaction_id=transaction_id,
        reason=reason,
    )


@mcp.tool()
def get_flagged_transactions(user_id: str) -> dict:
    """List all transactions currently flagged as fraud for the given user."""
    return safe_mcp_call(
        "get_flagged_transactions", _get_flagged_transactions, user_id=user_id
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
