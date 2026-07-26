"""
Phase 9 — MCP Platform Configuration.

All values are env-overridable for deployment-time tuning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class MCPServerConfig:
    """Per-server configuration entry."""

    name: str  # unique server name e.g. "bank-account-server"
    script_path: str  # path to the server .py file (relative to project root)
    enabled: bool = True
    timeout_seconds: float = 30.0
    max_retries: int = 2
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class MCPPlatformConfig:
    # ── Discovery ────────────────────────────────────────────────────────────
    auto_discover: bool = True  # scan mcp_servers/ on startup
    mcp_servers_dir: str = "mcp_servers"

    # ── Connection ───────────────────────────────────────────────────────────
    default_timeout: float = 30.0
    max_retries: int = 2
    retry_delay: float = 1.0

    # ── Execution ────────────────────────────────────────────────────────────
    max_concurrent_tools: int = 3  # max parallel tool calls
    normalize_errors: bool = True  # wrap raw errors into standard format

    # ── Tool selection ────────────────────────────────────────────────────────
    min_confidence_for_mcp: float = (
        0.60  # only invoke MCP if routing confidence >= this
    )
    preferred_servers: list[str] = field(default_factory=list)
    disabled_servers: list[str] = field(default_factory=list)

    # ── Integration ───────────────────────────────────────────────────────────
    feed_results_to_memory: bool = True  # store MCP tool results in memory engine
    feed_results_to_prompt: bool = True  # inject results into next turn context

    # ── Static server definitions (used when auto_discover=False) ────────────
    servers: list[MCPServerConfig] = field(
        default_factory=lambda: [
            MCPServerConfig(
                name="bank-account-server",
                script_path="mcp_servers/account_server.py",
                description="Account balance and transaction history tools",
                tags=["account", "balance", "transactions"],
            ),
            MCPServerConfig(
                name="bank-faq-server",
                script_path="mcp_servers/faq_server.py",
                description="FAQ and policy document search tools",
                tags=["search", "faq", "policy"],
            ),
            MCPServerConfig(
                name="bank-fraud-server",
                script_path="mcp_servers/fraud_server.py",
                description="Card security and fraud reporting tools",
                tags=["fraud", "security", "card"],
            ),
        ]
    )


def get_mcp_config() -> MCPPlatformConfig:
    """Build MCP config from environment variables."""
    disabled_raw = os.environ.get("MCP_DISABLED_SERVERS", "")
    preferred_raw = os.environ.get("MCP_PREFERRED_SERVERS", "")

    return MCPPlatformConfig(
        auto_discover=os.environ.get("MCP_AUTO_DISCOVER", "true").lower() == "true",
        mcp_servers_dir=os.environ.get("MCP_SERVERS_DIR", "mcp_servers"),
        default_timeout=float(os.environ.get("MCP_DEFAULT_TIMEOUT", 30.0)),
        max_retries=int(os.environ.get("MCP_MAX_RETRIES", 2)),
        retry_delay=float(os.environ.get("MCP_RETRY_DELAY", 1.0)),
        max_concurrent_tools=int(os.environ.get("MCP_MAX_CONCURRENT", 3)),
        normalize_errors=os.environ.get("MCP_NORMALIZE_ERRORS", "true").lower()
        == "true",
        min_confidence_for_mcp=float(os.environ.get("MCP_MIN_CONFIDENCE", 0.60)),
        preferred_servers=[s.strip() for s in preferred_raw.split(",") if s.strip()],
        disabled_servers=[s.strip() for s in disabled_raw.split(",") if s.strip()],
        feed_results_to_memory=os.environ.get("MCP_FEED_MEMORY", "true").lower()
        == "true",
        feed_results_to_prompt=os.environ.get("MCP_FEED_PROMPT", "true").lower()
        == "true",
    )


_config: MCPPlatformConfig | None = None


def mcp_config() -> MCPPlatformConfig:
    global _config
    if _config is None:
        _config = get_mcp_config()
    return _config
