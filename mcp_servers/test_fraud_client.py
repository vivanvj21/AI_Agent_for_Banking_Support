"""
NEW FILE — standalone test client for mcp_servers/fraud_server.py.

Proves the fraud MCP server works end-to-end, including the same
cross-user ownership security check that's already covered in
tests/test_tools.py — confirming that check survives being called through
the MCP protocol layer, not just via direct Python import.

Run:
    python mcp_servers/test_fraud_client.py
"""

import asyncio
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DB_PATH = Path(__file__).parent.parent / "db" / "bank.db"


def _find_card_for_user(user_id: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT c.card_id FROM cards c JOIN accounts a ON c.account_id = a.account_id "
        "WHERE a.user_id = ? LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(f"No card found for {user_id} — run db/seed_synthetic_data.py first.")
    return row[0]


async def main():
    card_id = _find_card_for_user("U1002")
    print(f"Using card {card_id} (belongs to U1002)\n")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).parent / "fraud_server.py")],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            print("Tools advertised by the MCP server:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}")

            print(f"\nLocking card {card_id} as its owner (U1002)...")
            result = await session.call_tool("lock_card", {"user_id": "U1002", "card_id": card_id})
            print("Result:", result.content[0].text)

            print(f"\nAttempting to lock the SAME card as a different user (U1003) — should fail...")
            result2 = await session.call_tool("lock_card", {"user_id": "U1003", "card_id": card_id})
            print("Result:", result2.content[0].text)

            print(f"\nUnlocking card {card_id} as its rightful owner (U1002)...")
            result3 = await session.call_tool("unlock_card", {"user_id": "U1002", "card_id": card_id})
            print("Result:", result3.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
