"""
NEW FILE — standalone test client for mcp_servers/account_server.py.
Does not modify anything else in the project.

This launches the account_server.py as a subprocess over stdio (the standard
MCP transport for local tools), connects to it as a real MCP client, lists
its advertised tools, and calls get_balance for a real seeded user — proving
the whole client -> protocol -> server -> SQL round trip actually works,
not just that the code parses.

Run:
    python mcp_servers/test_client.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).parent / "account_server.py")],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            print("Tools advertised by the MCP server:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            print("\nCalling get_balance(user_id='U1002') over MCP...")
            result = await session.call_tool("get_balance", {"user_id": "U1002"})
            for block in result.content:
                if hasattr(block, "text"):
                    print("Result:", block.text)

            print("\nCalling get_transaction_history(user_id='U1002', limit=3) over MCP...")
            result2 = await session.call_tool(
                "get_transaction_history", {"user_id": "U1002", "limit": 3}
            )
            for block in result2.content:
                if hasattr(block, "text"):
                    print("Result:", block.text)


if __name__ == "__main__":
    asyncio.run(main())
