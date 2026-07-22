"""Shared MCP server helpers."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from db.init_db import ensure_database
from logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def safe_mcp_call(tool_name: str, func: Callable[..., dict], **kwargs: Any) -> dict:
    """Run an MCP tool with initialization, logging, and structured errors."""
    configure_logging()
    try:
        ensure_database(seed_demo_data=True)
        LOGGER.info("mcp_tool_start", extra={"tool": tool_name})
        result = func(**kwargs)
        if not isinstance(result, dict):
            return {"error": f"Tool {tool_name} returned an invalid response type."}
        LOGGER.info("mcp_tool_complete", extra={"tool": tool_name})
        return result
    except TypeError as exc:
        LOGGER.warning("mcp_tool_invalid_request", extra={"tool": tool_name})
        return {"error": "Invalid tool request.", "details": str(exc)}
    except Exception:
        LOGGER.exception("mcp_tool_failed", extra={"tool": tool_name})
        return {"error": "Tool execution failed. See server logs for details."}
