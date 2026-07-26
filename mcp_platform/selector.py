"""
Phase 9 — MCP Tool Selector.

Decides WHEN to invoke MCP tools based on:
  - User intent and message content
  - Routing confidence from the supervisor
  - Available tools in the registry
  - Configured minimum confidence threshold

This keeps MCP tool invocation logic out of the agents — agents remain
focused on response generation, and the orchestrator decides when to
augment with external data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass
class ToolInvocationPlan:
    """Represents a decision to call one or more MCP tools."""

    should_invoke: bool
    tool_calls: list[dict[str, Any]]  # [{"tool_name": str, "args": dict}]
    reasoning: str
    confidence: float = 0.0


def select_tools_for_turn(
    intent: str,
    message: str,
    routing_confidence: float,
    user_id: str | None,
    registry,
    config,
    verified: bool = False,
) -> ToolInvocationPlan:
    """
    Decide which MCP tools (if any) to invoke before the agent handles the turn.

    Strategy:
    1. Skip if confidence below threshold (not confident enough about intent).
    2. Skip if no available tools match the intent.
    3. Skip if tool requires verification and user is not verified.
    4. Build a minimal set of tool calls that would enrich the agent's context.

    Returns a ToolInvocationPlan. The orchestrator executes it and injects
    results into the prompt via format_results_for_prompt().
    """

    if routing_confidence < config.min_confidence_for_mcp:
        return ToolInvocationPlan(
            should_invoke=False,
            tool_calls=[],
            reasoning=f"Confidence {routing_confidence:.2f} below MCP threshold {config.min_confidence_for_mcp}",
            confidence=routing_confidence,
        )

    candidate_tools = registry.find_tools_for_intent(intent)
    if not candidate_tools:
        return ToolInvocationPlan(
            should_invoke=False,
            tool_calls=[],
            reasoning=f"No MCP tools registered for intent={intent!r}",
            confidence=routing_confidence,
        )

    # Filter to tools that are relevant for this message
    selected: list[dict[str, Any]] = []
    msg_lower = message.lower()

    for tool in candidate_tools:
        # Skip tools that require a user_id if we don't have one
        needs_user = _requires_user_id(tool.input_schema)
        if needs_user and not user_id:
            continue
        if needs_user and not verified:
            continue

        # Only pick tools relevant to the message
        if not _tool_is_relevant(tool, msg_lower, intent):
            continue

        # Build args (inject user_id where needed, leave rest for the agent)
        args = {}
        if needs_user and user_id:
            args["user_id"] = user_id

        selected.append(
            {
                "tool_name": tool.name,
                "server_name": tool.server_name,
                "args": args,
            }
        )

        # Limit to 2 pre-emptive tool calls to avoid inflating context
        if len(selected) >= 2:
            break

    if not selected:
        return ToolInvocationPlan(
            should_invoke=False,
            tool_calls=[],
            reasoning="No relevant tools after filtering",
            confidence=routing_confidence,
        )

    return ToolInvocationPlan(
        should_invoke=True,
        tool_calls=selected,
        reasoning=f"Selected {len(selected)} MCP tool(s) for intent={intent!r}",
        confidence=routing_confidence,
    )


def _requires_user_id(input_schema: dict) -> bool:
    """Check if the tool's schema has a required user_id field."""
    props = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    return "user_id" in props or "user_id" in required


def _tool_is_relevant(tool, message_lower: str, intent: str) -> bool:
    """
    Quick relevance check: tool name or description must match
    the intent or a keyword in the message.
    """
    name_lower = tool.name.lower()
    desc_lower = tool.description.lower()

    # Direct intent match via tags
    if intent in tool.tags:
        return True

    # Message-level keyword signal
    relevance_keywords = {
        "account": ["balance", "account", "money", "funds", "amount", "how much"],
        "fraud": ["lock", "freeze", "stolen", "lost", "fraud", "suspicious", "block"],
        "search": ["what", "how", "policy", "interest", "fee", "procedure"],
    }
    for kw in relevance_keywords.get(intent, []):
        if kw in message_lower or kw in name_lower or kw in desc_lower:
            return True

    return False
