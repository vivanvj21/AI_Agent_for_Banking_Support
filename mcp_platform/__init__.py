"""
Phase 9 — MCP Platform Package.

Public API::

    from mcp_platform import get_mcp_manager, MCPManager
    from mcp_platform.registry import MCPRegistry, MCPServerEntry, MCPToolEntry
    from mcp_platform.client import MCPClient
    from mcp_platform.executor import ToolExecutor, ToolResult
    from mcp_platform.config import MCPPlatformConfig, get_mcp_config
"""

from mcp_platform.config import MCPPlatformConfig, get_mcp_config
from mcp_platform.executor import ToolExecutor, ToolResult
from mcp_platform.manager import MCPManager, get_mcp_manager
from mcp_platform.registry import MCPRegistry, MCPServerEntry, MCPToolEntry

__all__ = [
    "MCPManager",
    "MCPPlatformConfig",
    "MCPRegistry",
    "MCPServerEntry",
    "MCPToolEntry",
    "ToolExecutor",
    "ToolResult",
    "get_mcp_config",
    "get_mcp_manager",
]
