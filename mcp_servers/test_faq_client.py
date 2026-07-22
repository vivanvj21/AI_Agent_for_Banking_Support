"""
NEW FILE — standalone test client for mcp_servers/faq_server.py.

Run:
    python mcp_servers/test_faq_client.py

Note: on first run this will trigger tools/faq_search.py's index-building
step if knowledge_base/chroma_store doesn't exist yet, using whichever
embedding provider tools/embeddings.py resolves to (Voyage AI if
VOYAGE_API_KEY is set, otherwise the local dev fallback — see that file's
docstring for what that tradeoff means for retrieval quality).
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
        args=[str(Path(__file__).parent / "faq_server.py")],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            print("Tools advertised by the MCP server:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            query = "what happens if I lose my card"
            print(f"\nCalling search_faq(query={query!r}) over MCP...")
            result = await session.call_tool("search_faq", {"query": query, "k": 2})
            print("Result:", result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
