"""
LangGraph state machine for the Autonomous Bank Assistant.

Phase 8 flow:

    START -> supervisor (classify intent + confidence scoring)
               |
               v
           memory (build rich context from memory engine)
               |
               v
           routing (confidence-based, with fallback chain)
               |
               +-- confidence=HIGH  -> direct agent route
               |
               +-- confidence=MED   -> route + flag for fallback if needed
               |
               +-- confidence=LOW   -> try agent, fallback to clarify
               |
               +-- confidence=NONE  -> clarify or human_handoff
"""

from langgraph.graph import END, StateGraph

from agents.account_agent import run_account_agent
from agents.collaborator import (
    collaborate,
    detect_collaboration_need,
)
from agents.fraud_agent import run_fraud_agent
from agents.orchestration_config import config as orch_config
from agents.prompt_builder import (
    build_account_prompt,
    build_fraud_prompt,
    build_search_prompt,
)
from agents.search_agent import run_search_agent
from agents.state import AgentState
from agents.supervisor import classify_with_confidence
from agents.verification import try_verify
from mcp_platform.manager import get_mcp_manager
from memory.manager import get_memory_manager
from observability.metadata import build_node_metadata
from observability.tracing import trace_node
from tools import memory


def supervisor_node(state: AgentState) -> AgentState:
    """Phase 8 — intelligent supervisor with confidence-based routing."""
    meta = build_node_metadata(
        node_name="supervisor",
        session_id=state.get("session_id"),
        turn=state.get("turn", 0),
    )
    with trace_node("supervisor", metadata=meta, tags=["node:supervisor"]):
        last_user_msg = state["messages"][-1]["content"]
        recent_intents = state.get("recent_intents") or []
        verified = state.get("verified", False)

        # Build conversation history for context-aware classification
        conv_history = state["messages"][-6:] if len(state["messages"]) > 1 else []

        decision = classify_with_confidence(
            message=last_user_msg,
            conversation_history=conv_history,
            recent_intents=recent_intents,
            verified=verified,
        )

        state["intent"] = decision.intent
        state["routing_decision"] = decision.to_dict()

        # Append intent to recent_intents history (keep last 10)
        updated_recent = (recent_intents + [decision.intent])[-10:]
        state["recent_intents"] = updated_recent
        state.setdefault("fallback_attempts", 0)

    return state


def memory_node(state: AgentState) -> AgentState:
    """Phase 6 — build rich memory context before routing to an agent."""
    session_id = state.get("session_id")
    user_id = state.get("user_id")
    last_user_msg = state["messages"][-1]["content"] if state["messages"] else ""
    if not session_id or not last_user_msg:
        return state
    try:
        mgr = get_memory_manager()
        ctx = mgr.get_context(
            query=last_user_msg,
            session_id=session_id,
            user_id=user_id,
        )
        state["memory_context"] = {
            "long_term_facts": ctx.long_term_facts,
            "summary": ctx.summary,
            "system_context": ctx.system_context,
            "token_estimate": ctx.token_estimate,
        }
    except Exception:
        import logging

        logging.getLogger(__name__).debug("memory_node_failed", exc_info=True)
        state.setdefault("memory_context", None)
    return state


def mcp_tool_node(state: AgentState) -> AgentState:
    """
    Phase 9 — Pre-emptive MCP tool execution.

    Runs after memory_node. If the supervisor has HIGH/MEDIUM confidence
    in the intent AND matching MCP tools exist, calls them proactively
    and injects results into state["mcp_context"] for the agent to use.

    This is non-blocking: any failure leaves mcp_context=None and the
    agent handles the turn using only memory + RAG context as before.
    """
    intent = state.get("intent", "unclear")
    routing = state.get("routing_decision") or {}
    confidence = routing.get("confidence", 0.0)
    user_id = state.get("user_id")
    verified = state.get("verified", False)
    session_id = state.get("session_id")
    last_user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    if not last_user_msg or intent == "unclear":
        return state

    try:
        mgr = get_mcp_manager()
        plan = mgr.plan_tool_calls(
            intent=intent,
            message=last_user_msg,
            routing_confidence=confidence,
            user_id=user_id,
            verified=verified,
        )
        if plan.should_invoke:
            results = mgr.execute_plan(
                plan,
                session_id=session_id,
                user_id=user_id,
            )
            context_text = mgr.format_for_prompt(results)
            state["mcp_context"] = context_text if context_text else None
        else:
            state.setdefault("mcp_context", None)
    except Exception:
        import logging

        logging.getLogger(__name__).debug("mcp_tool_node_failed", exc_info=True)
        state.setdefault("mcp_context", None)

    return state


def route_after_supervisor(state: AgentState) -> str:
    """Phase 8 — confidence-aware routing with fallback support."""
    intent = state.get("intent", "unclear")
    routing = state.get("routing_decision") or {}
    confidence = routing.get("confidence", 0.5)
    cfg = orch_config()

    # Below fallback threshold → always clarify
    if confidence < cfg.fallback_threshold:
        return "clarify"

    if intent == "search":
        return "search_agent"

    if intent in ("account", "fraud"):
        if state.get("verified"):
            return "account_agent" if intent == "account" else "fraud_agent"
        return "verify_gate"

    return "clarify"


def verify_gate_node(state: AgentState) -> AgentState:
    # If already verified, skip the context manager entirely.
    if state.get("verified"):
        return state

    meta = build_node_metadata(
        node_name="verify_gate",
        session_id=state.get("session_id"),
        intent=state.get("intent"),
        turn=state.get("turn", 0),
    )
    with trace_node("verify_gate", metadata=meta, tags=["node:verify_gate"]):
        last_user_msg = state["messages"][-1]["content"]
        result = try_verify(last_user_msg)

        if result.get("verified"):
            state["verified"] = True
            state["user_id"] = result["user_id"]
            if state.get("session_id"):
                memory.link_session_to_user(state["session_id"], result["user_id"])
        else:
            state["retry_count"] = state.get("retry_count", 0) + 1
            state["reply"] = result.get("error", "I couldn't verify your identity.")
    return state


def route_after_verify(state: AgentState) -> str:
    if state.get("verified"):
        return (
            state["intent"] + "_agent"
            if state["intent"] in ("account", "fraud")
            else "clarify"
        )
    if state.get("retry_count", 0) >= state.get("max_retries", 3):
        return "human_handoff"
    return "await_credentials"


def search_agent_node(state: AgentState) -> AgentState:
    meta = build_node_metadata(
        node_name="search_agent",
        session_id=state.get("session_id"),
        intent=state.get("intent"),
        turn=state.get("turn", 0),
    )
    with trace_node("search_agent", metadata=meta, tags=["node:search_agent"]):
        last_user_msg = state["messages"][-1]["content"]
        # Phase 8: use centralized prompt builder
        system_prompt = build_search_prompt(memory_context=state.get("memory_context"))
        reply = run_search_agent(
            last_user_msg,
            state["tool_calls_log"],
            state["turn"],
            system_prompt_override=system_prompt,
        )
        state["reply"] = reply
    return state


def account_agent_node(state: AgentState) -> AgentState:
    meta = build_node_metadata(
        node_name="account_agent",
        session_id=state.get("session_id"),
        intent=state.get("intent"),
        turn=state.get("turn", 0),
    )
    with trace_node("account_agent", metadata=meta, tags=["node:account_agent"]):
        last_user_msg = state["messages"][-1]["content"]
        # Phase 8: centralized prompt builder with memory
        system_prompt = build_account_prompt(memory_context=state.get("memory_context"))
        reply = run_account_agent(
            last_user_msg,
            state["user_id"],
            state["tool_calls_log"],
            state["turn"],
            session_id=state.get("session_id"),
            memory_context=state.get("memory_context"),
            system_prompt_override=system_prompt,
        )
        state["reply"] = reply
    return state


def fraud_agent_node(state: AgentState) -> AgentState:
    meta = build_node_metadata(
        node_name="fraud_agent",
        session_id=state.get("session_id"),
        intent=state.get("intent"),
        turn=state.get("turn", 0),
    )
    with trace_node("fraud_agent", metadata=meta, tags=["node:fraud_agent"]):
        last_user_msg = state["messages"][-1]["content"]
        # Phase 8: centralized prompt builder with memory
        system_prompt = build_fraud_prompt(memory_context=state.get("memory_context"))
        reply = run_fraud_agent(
            last_user_msg,
            state["user_id"],
            state["tool_calls_log"],
            state["turn"],
            system_prompt_override=system_prompt,
        )
        # Phase 8: check if collaboration is needed
        cfg = orch_config()
        if cfg.enable_multi_agent_collab:
            needs_collab, assisting = detect_collaboration_need(
                last_user_msg, "fraud", cfg.collab_trigger_keywords
            )
            if needs_collab and assisting:
                reply = collaborate(
                    primary_intent="fraud",
                    assisting_agents=assisting,
                    user_message=last_user_msg,
                    user_id=state.get("user_id"),
                    primary_result=reply,
                    tool_log=state["tool_calls_log"],
                    turn=state["turn"],
                )
        state["reply"] = reply
    return state


def clarify_node(state: AgentState) -> AgentState:
    with trace_node(
        "clarify",
        metadata=build_node_metadata(
            node_name="clarify",
            session_id=state.get("session_id"),
            turn=state.get("turn", 0),
        ),
    ):
        state["reply"] = (
            "I can help with general policy questions, checking your balance or "
            "transaction history, or security actions like locking a card or "
            "reporting fraud. Could you tell me a bit more about what you need?"
        )
    return state


def await_credentials_node(state: AgentState) -> AgentState:
    # reply already set by verify_gate_node
    return state


def human_handoff_node(state: AgentState) -> AgentState:
    with trace_node(
        "human_handoff",
        metadata=build_node_metadata(
            node_name="human_handoff",
            session_id=state.get("session_id"),
            turn=state.get("turn", 0),
        ),
    ):
        state["reply"] = (
            "I'm unable to verify your identity after multiple attempts. "
            "For your security, please contact support directly at 1800-XXX-XXXX "
            "or visit a branch with valid ID."
        )
        state["end_session"] = True
    return state


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("memory", memory_node)  # Phase 6
    graph.add_node("mcp_tools", mcp_tool_node)  # Phase 9
    graph.add_node("verify_gate", verify_gate_node)
    graph.add_node("search_agent", search_agent_node)
    graph.add_node("account_agent", account_agent_node)
    graph.add_node("fraud_agent", fraud_agent_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("await_credentials", await_credentials_node)
    graph.add_node("human_handoff", human_handoff_node)

    graph.set_entry_point("supervisor")

    # Supervisor → memory → mcp_tools → routing
    graph.add_edge("supervisor", "memory")
    graph.add_edge("memory", "mcp_tools")

    graph.add_conditional_edges(
        "mcp_tools",
        lambda s: route_after_supervisor(s),
        {
            "search_agent": "search_agent",
            "verify_gate": "verify_gate",
            "clarify": "clarify",
            "account_agent": "account_agent",
            "fraud_agent": "fraud_agent",
        },
    )

    graph.add_conditional_edges(
        "verify_gate",
        route_after_verify,
        {
            "account_agent": "account_agent",
            "fraud_agent": "fraud_agent",
            "clarify": "clarify",
            "await_credentials": "await_credentials",
            "human_handoff": "human_handoff",
        },
    )

    graph.add_edge("search_agent", END)
    graph.add_edge("account_agent", END)
    graph.add_edge("fraud_agent", END)
    graph.add_edge("clarify", END)
    graph.add_edge("await_credentials", END)
    graph.add_edge("human_handoff", END)

    return graph.compile()


def new_session_state(channel: str = "cli") -> AgentState:
    """Start a brand new session and persist it immediately, so it survives
    even if the process dies before the first reply."""
    session_id = memory.create_session(channel=channel)
    # Phase 6: ensure memory tables exist
    try:
        get_memory_manager().ensure_ready()
    except Exception:
        pass
    # Phase 9: lazy-init MCP platform (skip discovery to avoid blocking session start)
    try:
        get_mcp_manager().initialize(skip_discovery=True)
    except Exception:
        pass
    return {
        "messages": [],
        "turn": 0,
        "session_id": session_id,
        "intent": None,
        "user_id": None,
        "verified": False,
        "retry_count": 0,
        "max_retries": 3,
        "tool_calls_log": [],
        "reply": None,
        "end_session": False,
        "memory_context": None,
        "mcp_context": None,
        # Phase 8: intelligent routing state
        "routing_decision": None,
        "recent_intents": [],
        "fallback_attempts": 0,
    }


def resume_session(session_id: str) -> AgentState:
    """
    Rebuild an AgentState from a previously-persisted session_id -- e.g. the
    CLI was killed mid-conversation, or Streamlit's process restarted.
    Replays saved messages and re-attaches verified/user_id if the session
    was already linked to a user.
    """
    if not memory.session_exists(session_id):
        return new_session_state()

    messages = memory.load_session_messages(session_id)
    user_id = memory.get_session_user(session_id)
    turn = sum(1 for m in messages if m["role"] == "user")

    return {
        "messages": messages[-memory.MAX_HISTORY_MESSAGES :],
        "turn": turn,
        "session_id": session_id,
        "intent": None,
        "user_id": user_id,
        "verified": bool(user_id),
        "retry_count": 0,
        "max_retries": 3,
        "tool_calls_log": [],
        "reply": None,
        "end_session": False,
        "memory_context": None,
        "mcp_context": None,
        # Phase 8: intelligent routing state
        "routing_decision": None,
        "recent_intents": [],
        "fallback_attempts": 0,
    }


def persist_turn(state: AgentState, user_msg: str) -> None:
    """Write the just-completed user turn + assistant reply to storage.
    Call this right after app.invoke() returns."""
    session_id = state.get("session_id")
    if not session_id:
        return
    memory.append_message(session_id, state["turn"], "user", user_msg)
    if state.get("reply"):
        memory.append_message(session_id, state["turn"], "assistant", state["reply"])

    # Phase 6: record turns in MemoryManager for semantic indexing
    user_id = state.get("user_id")
    try:
        mgr = get_memory_manager()
        mgr.record_turn(session_id, user_id, "user", user_msg)
        if state.get("reply"):
            mgr.record_turn(session_id, user_id, "assistant", state["reply"])
    except Exception:
        import logging

        logging.getLogger(__name__).debug("memory_record_turn_failed", exc_info=True)
