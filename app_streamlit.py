"""
Streamlit chat front-end for the Autonomous Bank Assistant.

Run: streamlit run app_streamlit.py

Demo users (see db/seed_synthetic_data.py): U1001..U1008, PINs 1111, 1222, ...
"""

from __future__ import annotations

import logging

import streamlit as st

from config import MissingAPIKeyError, validate_startup
from graph import build_graph, new_session_state, persist_turn, resume_session
from logging_config import configure_logging

configure_logging()
LOGGER = logging.getLogger(__name__)

st.set_page_config(page_title="Autonomous Bank Assistant", page_icon="🏦")
st.title("🏦 Autonomous Bank Assistant")
st.caption(
    'Demo agent — try: *"What happens if I lose my card?"* or '
    '*"What\'s my balance? U1002, 1222"*'
)

if "startup_status" not in st.session_state:
    st.session_state.startup_status = validate_startup(
        require_llm=True, initialize=True
    )

startup = st.session_state.startup_status
if not startup.ok:
    LOGGER.error(
        "streamlit_startup_validation_failed", extra={"details": startup.details}
    )
    st.error("The assistant is not configured correctly yet.")
    st.info(startup.message)
    st.caption("Technical details were written to logs/bank_assistant.log.")
    st.stop()

query_sid = st.query_params.get("sid")

try:
    if "graph_app" not in st.session_state:
        st.session_state.graph_app = build_graph()
    if "state" not in st.session_state:
        if query_sid:
            st.session_state.state = resume_session(query_sid)
        else:
            st.session_state.state = new_session_state(channel="streamlit")
        st.query_params["sid"] = st.session_state.state["session_id"]
    if "display_history" not in st.session_state:
        st.session_state.display_history = [
            (m["role"] if m["role"] == "user" else "assistant", m["content"])
            for m in st.session_state.state["messages"]
        ]
except Exception as exc:
    LOGGER.exception("streamlit_session_initialization_failed")
    st.error("Unable to start or resume the chat session.")
    st.info(str(exc))
    st.stop()

for role, content in st.session_state.display_history:
    with st.chat_message(role):
        st.write(content)

with st.sidebar:
    st.subheader("Session info")
    st.write("Session ID:", st.session_state.state.get("session_id"))
    st.write("Verified:", st.session_state.state.get("verified"))
    st.write("User ID:", st.session_state.state.get("user_id"))
    st.write("Turn:", st.session_state.state.get("turn"))
    st.caption(
        "This conversation is saved automatically -- refreshing the page will reconnect to it."
    )
    st.subheader("Startup checks")
    for name, status in startup.details.items():
        st.write(f"{name}: {status}")
    if st.button("Show tool-call log"):
        if not st.session_state.state["tool_calls_log"]:
            st.caption("No tool calls recorded yet.")
        for entry in st.session_state.state["tool_calls_log"]:
            st.code(
                f"[{entry['turn']}] {entry['agent']} -> {entry['tool']}({entry['args']})\n"
                f"=> {entry['result_summary']}"
            )
    if st.button("Start new session"):
        try:
            st.session_state.state = new_session_state(channel="streamlit")
            st.session_state.display_history = []
            st.query_params["sid"] = st.session_state.state["session_id"]
            LOGGER.info("streamlit_new_session")
            st.rerun()
        except Exception as exc:
            LOGGER.exception("streamlit_new_session_failed")
            st.error("Could not start a new session.")
            st.info(str(exc))

user_input = st.chat_input("Type your message...")
if user_input:
    st.session_state.display_history.append(("user", user_input))
    with st.chat_message("user"):
        st.write(user_input)

    state = st.session_state.state
    state["turn"] += 1
    state["messages"].append({"role": "user", "content": user_input})
    state["reply"] = None

    try:
        with st.spinner("Thinking..."):
            LOGGER.info("streamlit_turn_start", extra={"turn": state["turn"]})
            state = st.session_state.graph_app.invoke(state)
        persist_turn(state, user_input)
        st.session_state.state = state
        LOGGER.info("streamlit_turn_complete", extra={"turn": state["turn"]})
    except MissingAPIKeyError as exc:
        LOGGER.warning("streamlit_missing_api_key")
        st.error("Missing LLM configuration.")
        st.info(str(exc))
        st.stop()
    except Exception:
        LOGGER.exception("streamlit_turn_failed")
        state["reply"] = "Sorry, something went wrong while processing that request."
        st.session_state.state = state

    with st.chat_message("assistant"):
        st.write(state["reply"])
    st.session_state.display_history.append(("assistant", state["reply"]))

    if state.get("end_session"):
        st.warning("Session ended by assistant.")
