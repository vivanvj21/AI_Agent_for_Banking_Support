"""
Phase 9 — MCP Client.

Wraps the MCP Python SDK's ClientSession / StdioServerParameters to provide
a clean, high-level interface for calling tools on MCP servers.

Design decisions:
  - Each call opens + closes a subprocess connection (stateless).
    This avoids managing long-lived subprocess state in a web server process.
  - Synchronous API via asyncio.run() for compatibility with the existing
    synchronous LangGraph graph nodes.
  - All errors are normalized into a standard MCPCallError dict rather than
    raising, so callers never need to handle subprocess exceptions directly.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent


class MCPCallError(Exception):
    """Raised when an MCP tool call fails irrecoverably."""


async def _call_tool_async(
    script_path: str,
    tool_name: str,
    tool_args: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Internal async implementation that:
    1. Spawns the MCP server process via stdio transport
    2. Initializes the client session
    3. Calls the named tool with the provided arguments
    4. Returns the parsed result dict
    5. Cleans up the subprocess

    All under a hard timeout.
    """
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        raise MCPCallError("mcp package not installed. Run: pip install mcp")

    abs_script = _PROJECT_ROOT / script_path
    if not abs_script.exists():
        raise MCPCallError(f"MCP server script not found: {abs_script}")

    server_params = StdioServerParameters(
        command="python",
        args=[str(abs_script)],
        env=None,
    )

    async with asyncio.timeout(timeout):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, tool_args)
                # MCP SDK returns a CallToolResult; extract content
                if hasattr(result, "content") and result.content:
                    # Each content item may be TextContent, ImageContent, etc.
                    parts = []
                    for item in result.content:
                        if hasattr(item, "text"):
                            parts.append(item.text)
                        elif hasattr(item, "data"):
                            parts.append(str(item.data))
                    raw = " ".join(parts)
                    # Try to parse as JSON dict; fall back to string wrapper
                    import json

                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            return parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
                    return {"result": raw}
                return {"result": None}


class MCPClient:
    """
    Synchronous MCP tool caller.

    Usage::

        client = MCPClient(
            script_path="mcp_servers/account_server.py",
            server_name="bank-account-server",
            timeout=30.0,
        )
        result = client.call("get_balance", {"user_id": "U1001"})
    """

    def __init__(
        self,
        script_path: str,
        server_name: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> None:
        self.script_path = script_path
        self.server_name = server_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def call(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call a tool synchronously with retry logic.

        Returns a dict. On failure, returns {"error": "...", "details": "..."}.
        Never raises.
        """
        args = tool_args or {}
        last_error: str = ""

        for attempt in range(self.max_retries + 1):
            try:
                start = time.perf_counter()
                result = asyncio.run(
                    _call_tool_async(self.script_path, tool_name, args, self.timeout)
                )
                elapsed = time.perf_counter() - start
                LOGGER.info(
                    "mcp_client_call_ok",
                    extra={
                        "server": self.server_name,
                        "tool": tool_name,
                        "elapsed_ms": round(elapsed * 1000),
                        "attempt": attempt,
                    },
                )
                return result

            except asyncio.TimeoutError:
                last_error = f"Tool call timed out after {self.timeout}s"
                LOGGER.warning(
                    "mcp_client_timeout",
                    extra={
                        "server": self.server_name,
                        "tool": tool_name,
                        "attempt": attempt,
                    },
                )
            except MCPCallError as exc:
                last_error = str(exc)
                LOGGER.error(
                    "mcp_client_call_error",
                    extra={
                        "server": self.server_name,
                        "tool": tool_name,
                        "error": last_error,
                    },
                )
                break  # no point retrying config errors
            except Exception as exc:
                last_error = str(exc)
                LOGGER.warning(
                    "mcp_client_call_failed",
                    extra={
                        "server": self.server_name,
                        "tool": tool_name,
                        "attempt": attempt,
                        "error": last_error,
                    },
                )

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        return {
            "error": f"MCP tool call failed after {self.max_retries + 1} attempt(s)",
            "details": last_error,
            "server": self.server_name,
            "tool": tool_name,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        """
        Query the server for its available tools.
        Returns a list of tool descriptors, or [] on failure.
        """

        async def _list_async():
            try:
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
            except ImportError:
                return []
            abs_script = _PROJECT_ROOT / self.script_path
            if not abs_script.exists():
                return []
            params = StdioServerParameters(command="python", args=[str(abs_script)])
            async with asyncio.timeout(self.timeout):
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        tools = []
                        for t in tools_result.tools or []:
                            tools.append(
                                {
                                    "name": t.name,
                                    "description": getattr(t, "description", ""),
                                    "input_schema": (
                                        t.inputSchema.model_dump()
                                        if hasattr(t, "inputSchema") and t.inputSchema
                                        else {}
                                    ),
                                }
                            )
                        return tools

        try:
            return asyncio.run(_list_async())
        except Exception as exc:
            LOGGER.warning(
                "mcp_client_list_tools_failed",
                extra={"server": self.server_name, "error": str(exc)},
            )
            return []
