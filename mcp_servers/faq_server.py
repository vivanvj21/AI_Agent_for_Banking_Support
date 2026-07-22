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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from tools.faq_search import search_faq as _search_faq

mcp = FastMCP("bank-faq-server")


@mcp.tool()
def search_faq(query: str, k: int = 3) -> dict:
    """
    Semantic search over the bank's FAQ/policy knowledge base.
    Returns top-k chunks with their source doc name.
    """
    return _search_faq(query=query, k=k)


if __name__ == "__main__":
    mcp.run(transport="stdio")
