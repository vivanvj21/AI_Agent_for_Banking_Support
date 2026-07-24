"""
LangGraph state machine for the Autonomous Bank Assistant.

Flow:

    START -> supervisor (classify intent)
               |
               +-- intent=search  -----------------> search_agent -> END
               |
               +-- intent=account/fraud -> verify_gate
               |                              |
               |                              +-- already verified / just verified -> account_agent or fraud_agent -> END
               |                              +-- verification failed -> ask_for_credentials -> END (waits for next turn)
               |
               +-- intent=unclear -> clarify -> END

The verify_gate is a deterministic Python function, not an LLM decision --
see agents/verification.py for why that matters.

retry_count / max_retries in state prevent infinite loops if, e.g., a tool
call keeps failing -- after max_retries the graph routes to a human-handoff
message instead of looping the LLM again.
"""

from langgraph.graph import END, StateGraph

from agents.account_agent import run_account_agent
from agents.fraud_agent import run_fraud_agent
from agents.search_agent import run_search_agent
from agents.state import AgentState
from agents.supervisor import classify_intent
from agents.verification import try_verify
from observability.metadata import build_node_metadata
from observability.tracing import trace_node
from tools import memory


def supervisor_node(state: AgentState) -> AgentState:
    meta = build_node_metadata(
        node_name="supervisor",
        session_id=state.get("session_id"),
        turn=state.get("turn", 0),
    )
    with trace_node("supervisor", metadata=meta, tags=["node:supervisor"]):
        last_user_msg = state["messages"][-1]["content"]
        intent = classify_intent(last_user_msg)
        state["intent"] = intent
    return state


def route_after_supervisor(state: AgentState) -> str:
    intent = state.get("intent", "unclear")
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
        reply = run_search_agent(last_user_msg, state["tool_calls_log"], state["turn"])
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
        reply = run_account_agent(
            last_user_msg,
            state["user_id"],
            state["tool_calls_log"],
            state["turn"],
            session_id=state.get("session_id"),
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
        reply = run_fraud_agent(
            last_user_msg, state["user_id"], state["tool_calls_log"], state["turn"]
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
    graph.add_node("verify_gate", verify_gate_node)
    graph.add_node("search_agent", search_agent_node)
    graph.add_node("account_agent", account_agent_node)
    graph.add_node("fraud_agent", fraud_agent_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("await_credentials", await_credentials_node)
    graph.add_node("human_handoff", human_handoff_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
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
