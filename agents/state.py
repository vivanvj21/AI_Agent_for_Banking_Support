"""
Shared graph state. Kept as a plain TypedDict so it's easy to log/serialize
for the eval harness and the tool_calls_log deliverable.
"""

from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

Intent = Literal["search", "account", "fraud", "unclear"]


class ToolCallLogEntry(TypedDict):
    turn: int
    agent: str
    tool: str
    args: dict
    result_summary: str


class AgentState(TypedDict):
    # conversation
    messages: list[dict]  # [{"role": "user"/"assistant", "content": "..."}]
    turn: int

    # memory / persistence -- see tools/memory.py and memory/manager.py
    session_id: NotRequired[str]

    # Phase 6: assembled memory context for the current turn
    # Contains long_term_facts, summary, conversation_history from MemoryManager
    memory_context: NotRequired[dict[str, Any] | None]

    # Phase 9: MCP tool results injected as context before agent response
    mcp_context: NotRequired[str | None]

    # routing
    intent: NotRequired[Intent | None]

    # Phase 8: confidence-based routing
    routing_decision: NotRequired[dict[str, Any] | None]  # RoutingDecision.to_dict()
    recent_intents: NotRequired[list[str]]  # intent history for context boost
    fallback_attempts: NotRequired[int]  # how many fallbacks tried so far

    # identity / auth
    user_id: NotRequired[str | None]
    verified: bool

    # loop / failure control
    retry_count: int
    max_retries: int

    # observability
    tool_calls_log: list[ToolCallLogEntry]

    # the final reply to show the user this turn
    reply: NotRequired[str | None]

    # set True to end the conversation loop (CLI checks this)
    end_session: NotRequired[bool]
