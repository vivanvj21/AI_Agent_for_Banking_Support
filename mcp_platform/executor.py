"""
Phase 9 — MCP Tool Executor.

Provides a normalized execution layer over the MCP Client:
  - Validates tool calls against the registry
  - Routes to the correct server
  - Applies timeout and retry policy from config
  - Normalizes all responses and errors into ToolResult
  - Optionally feeds results to the Memory Engine
  - Records call metrics in the registry
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Normalized result from any MCP tool call."""

    tool_name: str
    server_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    def to_prompt_text(self) -> str:
        """Format for injection into agent prompts."""
        if not self.success:
            return f"[MCP tool {self.tool_name} failed: {self.error}]"
        import json

        return f"[MCP {self.tool_name} result]\n{json.dumps(self.data, indent=2)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool_name,
            "server": self.server_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


class ToolExecutor:
    """
    Central execution layer for MCP tool calls.

    Usage::

        executor = ToolExecutor(registry, platform_config)
        result = executor.execute("get_balance", {"user_id": "U1001"})
        print(result.to_prompt_text())
    """

    def __init__(self, registry, platform_config) -> None:
        from mcp_platform.config import MCPPlatformConfig
        from mcp_platform.registry import MCPRegistry

        self._registry: MCPRegistry = registry
        self._config: MCPPlatformConfig = platform_config

    def execute(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
        server_name: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> ToolResult:
        """
        Execute a tool by name.

        Resolution order:
          1. If server_name given, use that server directly.
          2. Otherwise find the server via registry.find_server_for_tool().
          3. If no server found, return error ToolResult.

        After execution, feeds result into Memory Engine if configured.
        """
        start = time.perf_counter()

        # ── Resolve server ────────────────────────────────────────────────────
        from mcp_platform.registry import ServerStatus

        server = None
        if server_name:
            server = self._registry.get_server(server_name)
        if server is None:
            server = self._registry.find_server_for_tool(tool_name)

        if server is None:
            return ToolResult(
                tool_name=tool_name,
                server_name=server_name or "unknown",
                success=False,
                error=f"No MCP server found for tool '{tool_name}'",
                elapsed_ms=0.0,
            )

        if server.status != ServerStatus.AVAILABLE:
            return ToolResult(
                tool_name=tool_name,
                server_name=server.name,
                success=False,
                error=f"Server '{server.name}' is {server.status.value}: {server.error_message}",
                elapsed_ms=0.0,
            )

        # ── Execute via MCP Client ────────────────────────────────────────────
        from mcp_platform.client import MCPClient

        client = MCPClient(
            script_path=server.script_path,
            server_name=server.name,
            timeout=self._config.default_timeout,
            max_retries=self._config.max_retries,
            retry_delay=self._config.retry_delay,
        )

        raw_result = client.call(tool_name, tool_args or {})
        elapsed = (time.perf_counter() - start) * 1000
        success = "error" not in raw_result

        result = ToolResult(
            tool_name=tool_name,
            server_name=server.name,
            success=success,
            data=raw_result if success else {},
            error=raw_result.get("error", "") if not success else "",
            elapsed_ms=elapsed,
            raw=raw_result,
        )

        # ── Record metrics ────────────────────────────────────────────────────
        qualified = f"{server.name}/{tool_name}"
        self._registry.record_call(qualified, success)

        LOGGER.info(
            "mcp_executor_result",
            extra={
                "tool": tool_name,
                "server": server.name,
                "success": success,
                "elapsed_ms": round(elapsed, 1),
            },
        )

        # ── Feed result to Memory Engine ──────────────────────────────────────
        if success and self._config.feed_results_to_memory and session_id:
            self._feed_to_memory(result, session_id, user_id)

        return result

    def execute_many(
        self,
        calls: list[dict[str, Any]],
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> list[ToolResult]:
        """
        Execute multiple tool calls sequentially.
        Each call: {"tool_name": str, "args": dict, "server_name": str | None}
        """
        results = []
        for call in calls:
            r = self.execute(
                tool_name=call["tool_name"],
                tool_args=call.get("args", {}),
                server_name=call.get("server_name"),
                session_id=session_id,
                user_id=user_id,
            )
            results.append(r)
        return results

    def _feed_to_memory(
        self,
        result: ToolResult,
        session_id: str,
        user_id: str | None,
    ) -> None:
        """Store MCP tool result in the Memory Engine as a long-term fact."""
        try:
            from memory.manager import get_memory_manager

            mgr = get_memory_manager()
            content = f"MCP tool {result.tool_name} returned: {str(result.data)[:300]}"
            mgr.record_turn(
                session_id=session_id,
                user_id=user_id,
                role="tool",
                content=content,
                metadata={
                    "tool_name": result.tool_name,
                    "server_name": result.server_name,
                    "mcp": True,
                },
            )
        except Exception:
            LOGGER.debug("mcp_executor_memory_feed_failed", exc_info=True)


def format_results_for_prompt(results: list[ToolResult]) -> str:
    """Format a list of ToolResults for injection into an agent prompt."""
    if not results:
        return ""
    parts = ["[External tool results]"]
    for r in results:
        parts.append(r.to_prompt_text())
    return "\n\n".join(parts)
