"""
Conversation and request metadata builders for LangSmith traces.

Every LangSmith run can carry arbitrary ``metadata`` and ``tags`` dicts.
This module provides typed builders so every call-site attaches the same
rich, consistent set of fields, making filtering and dashboards easy.

Usage:
    from observability.metadata import build_conversation_metadata, build_rag_metadata

    meta = build_conversation_metadata(
        session_id="abc123",
        channel="cli",
        turn=3,
        intent="account",
    )
    # meta = {
    #   "session_id": "abc123",
    #   "channel": "cli",
    #   "turn": 3,
    #   "intent": "account",
    #   "timestamp": "2024-01-15T10:30:00Z",
    #   ...
    # }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_conversation_metadata(
    *,
    session_id: str | None = None,
    channel: str = "unknown",
    turn: int = 0,
    intent: str | None = None,
    agent: str | None = None,
    verified: bool = False,
    retrieval_enabled: bool = False,
    memory_enabled: bool = True,
    conversation_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a metadata dict for a full conversation turn trace.

    Args:
        session_id:        Unique session identifier (no PII).
        channel:           "cli", "fastapi", or "streamlit".
        turn:              Zero-based turn counter.
        intent:            Classified intent: search | account | fraud | unclear.
        agent:             Agent that handled this turn.
        verified:          True if user has been authenticated this session.
        retrieval_enabled: True if RAG was invoked.
        memory_enabled:    True if session memory was consulted.
        conversation_id:   Optional conversation-level grouping ID.
        extra:             Any additional key-value pairs to merge in.

    Returns:
        Flat metadata dict safe to attach to any LangSmith run.
    """
    meta: dict[str, Any] = {
        "timestamp": _now_iso(),
        "channel": channel,
        "turn": turn,
        "verified": verified,
        "retrieval_enabled": retrieval_enabled,
        "memory_enabled": memory_enabled,
    }
    if session_id:
        meta["session_id"] = session_id
    if conversation_id:
        meta["conversation_id"] = conversation_id
    if intent:
        meta["intent"] = intent
    if agent:
        meta["agent"] = agent
    if extra:
        meta.update(extra)
    return meta


def build_rag_metadata(
    *,
    query: str,
    normalized_query: str,
    num_results: int,
    retrieval_method: str = "hybrid_rrf_mmr",
    sources: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a metadata dict for a RAG retrieval trace.

    Args:
        query:             Raw user query (will NOT be stored if sensitive).
        normalized_query:  Query after preprocessing/normalisation.
        num_results:       Number of chunks retrieved.
        retrieval_method:  Pipeline variant string for analysis.
        sources:           List of source document names returned.
        extra:             Additional metadata.

    Returns:
        Flat metadata dict.
    """
    meta: dict[str, Any] = {
        "timestamp": _now_iso(),
        "query_length": len(query),
        "normalized_query_length": len(normalized_query),
        "num_results": num_results,
        "retrieval_method": retrieval_method,
    }
    if sources:
        meta["sources"] = sources
    if extra:
        meta.update(extra)
    return meta


def build_tool_metadata(
    *,
    tool_name: str,
    agent: str,
    turn: int,
    session_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metadata for a single tool-call trace.

    Args:
        tool_name:  Name of the tool being called.
        agent:      Agent that triggered the tool.
        turn:       Current conversation turn.
        session_id: Optional session identifier.
        extra:      Additional metadata.

    Returns:
        Flat metadata dict.
    """
    meta: dict[str, Any] = {
        "timestamp": _now_iso(),
        "tool_name": tool_name,
        "agent": agent,
        "turn": turn,
    }
    if session_id:
        meta["session_id"] = session_id
    if extra:
        meta.update(extra)
    return meta


def build_llm_metadata(
    *,
    model: str,
    agent: str,
    turn: int,
    session_id: str | None = None,
    temperature: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metadata for an LLM request trace.

    Args:
        model:       Model identifier (e.g. "claude-sonnet-4-5").
        agent:       Agent making the LLM call.
        turn:        Current conversation turn.
        session_id:  Optional session identifier.
        temperature: Sampling temperature, if set.
        extra:       Additional metadata.

    Returns:
        Flat metadata dict.
    """
    meta: dict[str, Any] = {
        "timestamp": _now_iso(),
        "model": model,
        "agent": agent,
        "turn": turn,
    }
    if session_id:
        meta["session_id"] = session_id
    if temperature is not None:
        meta["temperature"] = temperature
    if extra:
        meta.update(extra)
    return meta


def build_node_metadata(
    *,
    node_name: str,
    session_id: str | None = None,
    intent: str | None = None,
    turn: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metadata for a LangGraph node trace.

    Args:
        node_name:  Name of the graph node (e.g. "supervisor", "search_agent").
        session_id: Optional session identifier.
        intent:     Intent value at the time the node ran.
        turn:       Current conversation turn.
        extra:      Additional metadata.

    Returns:
        Flat metadata dict.
    """
    meta: dict[str, Any] = {
        "timestamp": _now_iso(),
        "node_name": node_name,
        "turn": turn,
    }
    if session_id:
        meta["session_id"] = session_id
    if intent:
        meta["intent"] = intent
    if extra:
        meta.update(extra)
    return meta
