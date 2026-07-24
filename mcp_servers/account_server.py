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
from pathlib import Path

# Make the existing tools/ package importable from this new location
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from mcp_servers.common import safe_mcp_call
from tools.account_tools import get_balance as _get_balance
from tools.account_tools import get_transaction_history as _get_transaction_history

mcp = FastMCP("bank-account-server")


@mcp.tool()
def get_balance(user_id: str, account_id: str | None = None) -> dict:
    """
    Get balance for a specific account, or all accounts for a user if
    account_id is omitted. Wraps tools.account_tools.get_balance unchanged.
    """
    return safe_mcp_call(
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
    return safe_mcp_call(
        "get_transaction_history",
        _get_transaction_history,
        user_id=user_id,
        account_id=account_id,
        limit=limit,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
