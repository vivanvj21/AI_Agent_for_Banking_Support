"""
Phase 9 — MCP Tool Discovery.

Automatically discovers available tools from each registered MCP server
by querying their list_tools() endpoint at startup.

Avoids hardcoded tool registrations — adding a new @mcp.tool() to any
server script automatically surfaces it in the registry.

Discovery is best-effort: if a server is unavailable, it is marked
UNAVAILABLE but the rest of the platform continues normally.
"""

from __future__ import annotations

import logging
from pathlib import Path

from mcp_platform.config import MCPPlatformConfig, MCPServerConfig
from mcp_platform.registry import (
    MCPRegistry,
    MCPServerEntry,
    MCPToolEntry,
    ServerStatus,
    ToolStatus,
)

LOGGER = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent

# ── Intent → server tag mapping ───────────────────────────────────────────────
# Used to enrich discovered tools with intent routing hints

_SERVER_INTENT_MAP: dict[str, list[str]] = {
    "bank-account-server": ["account", "balance", "transactions"],
    "bank-faq-server": ["search", "faq", "policy"],
    "bank-fraud-server": ["fraud", "security", "card"],
}


def _infer_tags_from_server(server_name: str, tool_name: str) -> list[str]:
    """Infer routing tags from server and tool name."""
    tags: list[str] = []
    # Server-level intent tags
    tags.extend(_SERVER_INTENT_MAP.get(server_name, []))
    # Tool name hints
    if "balance" in tool_name or "account" in tool_name:
        tags.extend(["account"])
    if "transaction" in tool_name or "history" in tool_name:
        tags.extend(["account", "transactions"])
    if "faq" in tool_name or "search" in tool_name:
        tags.extend(["search", "faq"])
    if "fraud" in tool_name or "lock" in tool_name or "card" in tool_name:
        tags.extend(["fraud", "security"])
    return list(set(tags))


def discover_server(
    config: MCPServerConfig,
    registry: MCPRegistry,
    timeout: float = 15.0,
) -> bool:
    """
    Query a single MCP server for its tools and register everything in the registry.

    Returns True if discovery succeeded, False if the server is unavailable.
    Discovery failure is non-fatal — the server is marked UNAVAILABLE.
    """
    server_entry = MCPServerEntry(
        name=config.name,
        script_path=config.script_path,
        description=config.description,
        tags=config.tags or _SERVER_INTENT_MAP.get(config.name, []),
    )
    registry.register_server(server_entry)

    # Check script exists before spawning a subprocess
    script_abs = _PROJECT_ROOT / config.script_path
    if not script_abs.exists():
        registry.set_server_status(
            config.name,
            ServerStatus.UNAVAILABLE,
            f"Script not found: {config.script_path}",
        )
        LOGGER.warning(
            "mcp_discovery_script_missing",
            extra={"server": config.name, "path": config.script_path},
        )
        return False

    # Query the server for its tool list
    from mcp_platform.client import MCPClient

    client = MCPClient(
        script_path=config.script_path,
        server_name=config.name,
        timeout=timeout,
        max_retries=1,
    )

    tools_raw = client.list_tools()

    if not tools_raw:
        # Server launched but returned no tools — still mark available,
        # just with zero tools (server might be empty intentionally)
        LOGGER.warning(
            "mcp_discovery_no_tools",
            extra={"server": config.name},
        )
        # Attempt to mark available — if list_tools returned [], server did respond
        registry.set_server_status(
            config.name,
            ServerStatus.UNAVAILABLE,
            "No tools discovered or server failed to start",
        )
        return False

    # Register each discovered tool
    for tool_raw in tools_raw:
        tool_name = tool_raw.get("name", "")
        if not tool_name:
            continue
        tool = MCPToolEntry(
            name=tool_name,
            server_name=config.name,
            description=tool_raw.get("description", ""),
            input_schema=tool_raw.get("input_schema", {}),
            tags=_infer_tags_from_server(config.name, tool_name),
            status=ToolStatus.ACTIVE,
        )
        registry.add_tool(config.name, tool)

    registry.set_server_status(config.name, ServerStatus.AVAILABLE)
    LOGGER.info(
        "mcp_discovery_ok",
        extra={"server": config.name, "tools": len(tools_raw)},
    )
    return True


def discover_all(
    platform_config: MCPPlatformConfig,
    registry: MCPRegistry,
) -> dict[str, bool]:
    """
    Discover tools from all enabled servers.

    Returns a dict mapping server_name → discovery_success.
    """
    results: dict[str, bool] = {}
    disabled = set(platform_config.disabled_servers)

    for server_config in platform_config.servers:
        if not server_config.enabled or server_config.name in disabled:
            LOGGER.info(
                "mcp_discovery_skipped",
                extra={"server": server_config.name, "reason": "disabled"},
            )
            # Still register it as disabled
            entry = MCPServerEntry(
                name=server_config.name,
                script_path=server_config.script_path,
                description=server_config.description,
                tags=server_config.tags,
                status=ServerStatus.DISABLED,
            )
            registry.register_server(entry)
            registry.set_server_status(server_config.name, ServerStatus.DISABLED)
            results[server_config.name] = False
            continue

        try:
            ok = discover_server(
                server_config, registry, timeout=platform_config.default_timeout
            )
            results[server_config.name] = ok
        except Exception as exc:
            LOGGER.exception(
                "mcp_discovery_exception",
                extra={"server": server_config.name, "error": str(exc)},
            )
            registry.set_server_status(
                server_config.name,
                ServerStatus.UNAVAILABLE,
                str(exc),
            )
            results[server_config.name] = False

    return results
