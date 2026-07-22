"""
Shared graph state. Kept as a plain TypedDict so it's easy to log/serialize
for the eval harness and the tool_calls_log deliverable.
"""

from typing import TypedDict, Literal, Optional
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
    messages: list[dict]        # [{"role": "user"/"assistant", "content": "..."}]
    turn: int

    # memory / persistence -- see tools/memory.py
    session_id: NotRequired[str]

    # routing
    intent: NotRequired[Optional[Intent]]

    # identity / auth
    user_id: NotRequired[Optional[str]]
    verified: bool

    # loop / failure control
    retry_count: int
    max_retries: int

    # observability
    tool_calls_log: list[ToolCallLogEntry]

    # the final reply to show the user this turn
    reply: NotRequired[Optional[str]]

    # set True to end the conversation loop (CLI checks this)
    end_session: NotRequired[bool]
