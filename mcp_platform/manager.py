"""
Phase 9 — MCP Manager.

Central orchestrator for the MCP Platform layer.
Responsible for:
  - Initializing the registry
  - Running tool discovery on startup
  - Providing a unified interface for the graph/agents to call MCP tools
  - Exposing a singleton via get_mcp_manager()

Design: lazy initialization — the manager is only fully started when
first accessed, so importing mcp_platform never blocks the app startup.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_platform.config import MCPPlatformConfig, mcp_config
from mcp_platform.executor import ToolExecutor, ToolResult, format_results_for_prompt
from mcp_platform.registry import MCPRegistry

LOGGER = logging.getLogger(__name__)


class MCPManager:
    """
    Facade for the entire MCP Platform.

    Typical usage in graph nodes::

        mgr = get_mcp_manager()
        plan = mgr.plan_tool_calls(intent, message, confidence, user_id, verified)
        if plan.should_invoke:
            results = mgr.execute_plan(plan, session_id=session_id, user_id=user_id)
            context_text = mgr.format_for_prompt(results)
    """

    def __init__(self, config: MCPPlatformConfig | None = None) -> None:
        self._config = config or mcp_config()
        self._registry = MCPRegistry()
        self._executor = ToolExecutor(self._registry, self._config)
        self._initialized = False
        self._discovery_results: dict[str, bool] = {}

    def initialize(self, skip_discovery: bool = False) -> dict[str, bool]:
        """
        Run one-time startup: discover all MCP server tools.

        This is called by the FastAPI lifespan and by graph.new_session_state().
        Safe to call multiple times (idempotent after first call).

        Returns dict mapping server_name → discovery_success.
        """
        if self._initialized:
            return self._discovery_results

        LOGGER.info("mcp_manager_initializing")

        if skip_discovery:
            self._initialized = True
            return {}

        try:
            from mcp_platform.discovery import discover_all

            self._discovery_results = discover_all(self._config, self._registry)
        except Exception:
            LOGGER.exception("mcp_manager_discovery_failed")
            self._discovery_results = {}

        self._initialized = True

        available = sum(1 for ok in self._discovery_results.values() if ok)
        total = len(self._discovery_results)
        LOGGER.info(
            "mcp_manager_ready",
            extra={
                "servers_available": available,
                "servers_total": total,
                "tools_discovered": len(self._registry.all_tools()),
            },
        )
        return self._discovery_results

    # ── Tool planning ─────────────────────────────────────────────────────────

    def plan_tool_calls(
        self,
        intent: str,
        message: str,
        routing_confidence: float,
        user_id: str | None = None,
        verified: bool = False,
    ):
        """
        Decide which MCP tools to call for this turn.
        Returns a ToolInvocationPlan.
        """
        if not self._initialized:
            self.initialize()

        from mcp_platform.selector import select_tools_for_turn

        return select_tools_for_turn(
            intent=intent,
            message=message,
            routing_confidence=routing_confidence,
            user_id=user_id,
            registry=self._registry,
            config=self._config,
            verified=verified,
        )

    # ── Execution ─────────────────────────────────────────────────────────────

    def execute_plan(
        self,
        plan,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> list[ToolResult]:
        """Execute a ToolInvocationPlan and return results."""
        if not plan.should_invoke:
            return []
        return self._executor.execute_many(
            plan.tool_calls,
            session_id=session_id,
            user_id=user_id,
        )

    def call_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
        server_name: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> ToolResult:
        """Direct tool call — bypasses planning, useful for explicit agent requests."""
        if not self._initialized:
            self.initialize()
        return self._executor.execute(
            tool_name=tool_name,
            tool_args=tool_args,
            server_name=server_name,
            session_id=session_id,
            user_id=user_id,
        )

    # ── Context integration ───────────────────────────────────────────────────

    def format_for_prompt(self, results: list[ToolResult]) -> str:
        """Format tool results as a string block for agent prompt injection."""
        return format_results_for_prompt(results)

    # ── Registry queries (for supervisor/routing) ─────────────────────────────

    def get_tools_for_intent(self, intent: str) -> list[dict[str, Any]]:
        """Return available tools for a given intent as dicts."""
        return [t.to_dict() for t in self._registry.find_tools_for_intent(intent)]

    def get_registry_snapshot(self) -> dict[str, Any]:
        """Full registry snapshot for /metrics or debug endpoints."""
        return self._registry.snapshot()

    @property
    def is_ready(self) -> bool:
        return self._initialized

    @property
    def has_available_servers(self) -> bool:
        return len(self._registry.available_servers()) > 0


# ── Module-level singleton ────────────────────────────────────────────────────

_default_manager: MCPManager | None = None


def get_mcp_manager() -> MCPManager:
    """Return the process-wide MCPManager singleton."""
    global _default_manager
    if _default_manager is None:
        _default_manager = MCPManager()
    return _default_manager
