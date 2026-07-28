"""
Phase 9 — MCP Platform API routes.

Exposes MCP registry status and direct tool invocation endpoints
for debugging, monitoring, and external integrations.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import verify_perimeter_api_key

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"], dependencies=[Depends(verify_perimeter_api_key)])


class MCPToolCallRequest(BaseModel):
    tool_name: str
    tool_args: dict[str, Any] = {}
    server_name: str | None = None
    session_id: str | None = None
    user_id: str | None = None


class MCPToolCallResponse(BaseModel):
    tool_name: str
    server_name: str
    success: bool
    data: dict[str, Any] = {}
    error: str = ""
    elapsed_ms: float = 0.0


@router.get("/status", summary="MCP Platform status and registry snapshot")
def mcp_status() -> dict[str, Any]:
    """
    Returns the current state of the MCP registry:
    - registered servers and their status
    - discovered tools per server
    - call metrics
    """
    try:
        from mcp_platform.manager import get_mcp_manager

        mgr = get_mcp_manager()
        if not mgr.is_ready:
            return {"status": "not_initialized", "registry": {}}
        return {
            "status": "ready",
            "has_available_servers": mgr.has_available_servers,
            "registry": mgr.get_registry_snapshot(),
        }
    except Exception as exc:
        LOGGER.exception("mcp_status_failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tools", summary="List all discovered MCP tools")
def list_mcp_tools() -> dict[str, Any]:
    """Return all active MCP tools discovered at startup."""
    try:
        from mcp_platform.manager import get_mcp_manager
        from mcp_platform.registry import ToolStatus

        mgr = get_mcp_manager()
        registry = mgr._registry
        tools = [
            t.to_dict() for t in registry.all_tools() if t.status == ToolStatus.ACTIVE
        ]
        return {"tool_count": len(tools), "tools": tools}
    except Exception as exc:
        LOGGER.exception("mcp_list_tools_failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tools/{intent}", summary="List MCP tools for a given intent")
def tools_for_intent(intent: str) -> dict[str, Any]:
    """Return tools matching a routing intent (account | fraud | search)."""
    try:
        from mcp_platform.manager import get_mcp_manager

        mgr = get_mcp_manager()
        tools = mgr.get_tools_for_intent(intent)
        return {"intent": intent, "tool_count": len(tools), "tools": tools}
    except Exception as exc:
        LOGGER.exception("mcp_tools_for_intent_failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/call", response_model=MCPToolCallResponse, summary="Directly invoke an MCP tool"
)
def call_mcp_tool(payload: MCPToolCallRequest) -> MCPToolCallResponse:
    """
    Directly call an MCP tool by name. Useful for testing and integration.
    Note: some tools require user_id for authorization (e.g. get_balance).
    """
    try:
        from mcp_platform.manager import get_mcp_manager

        mgr = get_mcp_manager()
        result = mgr.call_tool(
            tool_name=payload.tool_name,
            tool_args=payload.tool_args,
            server_name=payload.server_name,
            session_id=payload.session_id,
            user_id=payload.user_id,
        )
        return MCPToolCallResponse(
            tool_name=result.tool_name,
            server_name=result.server_name,
            success=result.success,
            data=result.data,
            error=result.error,
            elapsed_ms=result.elapsed_ms,
        )
    except Exception as exc:
        LOGGER.exception("mcp_call_tool_failed")
        raise HTTPException(status_code=500, detail=str(exc))
