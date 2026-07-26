"""
Phase 9 — MCP Registry.

Maintains the live catalog of:
  - available MCP servers (discovered or statically configured)
  - tools exposed by each server
  - server/tool status and metadata

The registry is populated by the MCPManager on startup via tool discovery,
and is queried by the supervisor/orchestrator for tool selection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

LOGGER = logging.getLogger(__name__)


class ServerStatus(str, Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class ToolStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class MCPToolEntry:
    """Descriptor for a single tool exposed by an MCP server."""

    name: str  # tool function name e.g. "get_balance"
    server_name: str  # parent server name
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    status: ToolStatus = ToolStatus.ACTIVE
    call_count: int = 0
    error_count: int = 0

    @property
    def qualified_name(self) -> str:
        return f"{self.server_name}/{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "server_name": self.server_name,
            "description": self.description,
            "tags": self.tags,
            "status": self.status.value,
            "call_count": self.call_count,
        }


@dataclass
class MCPServerEntry:
    """Descriptor for a registered MCP server."""

    name: str  # e.g. "bank-account-server"
    script_path: str  # e.g. "mcp_servers/account_server.py"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    status: ServerStatus = ServerStatus.UNKNOWN
    tools: dict[str, MCPToolEntry] = field(default_factory=dict)
    error_message: str = ""

    def add_tool(self, tool: MCPToolEntry) -> None:
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> MCPToolEntry | None:
        return self.tools.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "script_path": self.script_path,
            "description": self.description,
            "tags": self.tags,
            "status": self.status.value,
            "tools": [t.to_dict() for t in self.tools.values()],
            "tool_count": len(self.tools),
        }


class MCPRegistry:
    """
    In-memory registry of all MCP servers and their tools.

    Lifecycle:
      1. MCPManager calls register_server() for each configured server.
      2. MCPManager calls add_tool() for each discovered tool.
      3. Supervisor queries find_tools_for_intent() / find_server() for routing.
      4. Executor calls record_call() after each tool invocation.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerEntry] = {}
        self._tool_index: dict[str, MCPToolEntry] = {}  # qualified_name → tool

    # ── Registration ─────────────────────────────────────────────────────────

    def register_server(self, server: MCPServerEntry) -> None:
        self._servers[server.name] = server
        LOGGER.debug("mcp_registry_server_registered", extra={"name": server.name})

    def add_tool(self, server_name: str, tool: MCPToolEntry) -> None:
        if server_name not in self._servers:
            LOGGER.warning("mcp_registry_unknown_server", extra={"server": server_name})
            return
        self._servers[server_name].add_tool(tool)
        self._tool_index[tool.qualified_name] = tool

    def set_server_status(
        self, name: str, status: ServerStatus, error: str = ""
    ) -> None:
        if name in self._servers:
            self._servers[name].status = status
            self._servers[name].error_message = error

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_server(self, name: str) -> MCPServerEntry | None:
        return self._servers.get(name)

    def all_servers(self) -> list[MCPServerEntry]:
        return list(self._servers.values())

    def available_servers(self) -> list[MCPServerEntry]:
        return [s for s in self._servers.values() if s.status == ServerStatus.AVAILABLE]

    def all_tools(self) -> list[MCPToolEntry]:
        return list(self._tool_index.values())

    def get_tool(self, qualified_name: str) -> MCPToolEntry | None:
        """Look up by 'server-name/tool-name'."""
        return self._tool_index.get(qualified_name)

    def find_tools_for_intent(self, intent: str) -> list[MCPToolEntry]:
        """
        Return active tools whose server tags or tool tags include the intent.
        Used by the supervisor for intent → MCP tool mapping.
        """
        results = []
        for server in self.available_servers():
            server_matches = intent in server.tags or any(
                intent in tag for tag in server.tags
            )
            for tool in server.tools.values():
                if tool.status != ToolStatus.ACTIVE:
                    continue
                tool_matches = intent in tool.tags or any(
                    intent in tag for tag in tool.tags
                )
                if server_matches or tool_matches:
                    results.append(tool)
        return results

    def find_tools_by_keyword(self, keyword: str) -> list[MCPToolEntry]:
        """Return tools whose name or description contains the keyword."""
        kw = keyword.lower()
        return [
            t
            for t in self.all_tools()
            if kw in t.name.lower() or kw in t.description.lower()
        ]

    def find_server_for_tool(self, tool_name: str) -> MCPServerEntry | None:
        """Find which server exposes a given bare tool name."""
        for server in self._servers.values():
            if tool_name in server.tools:
                return server
        return None

    # ── Metrics ───────────────────────────────────────────────────────────────

    def record_call(self, qualified_name: str, success: bool) -> None:
        tool = self._tool_index.get(qualified_name)
        if tool:
            tool.call_count += 1
            if not success:
                tool.error_count += 1

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        return {
            "server_count": len(self._servers),
            "available_servers": len(self.available_servers()),
            "total_tools": len(self._tool_index),
            "servers": [s.to_dict() for s in self._servers.values()],
        }
