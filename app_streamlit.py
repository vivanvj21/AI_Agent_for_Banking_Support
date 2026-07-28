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

state = st.session_state.state

if not state.get("verified") and state.get("intent") in ("account", "fraud"):
    st.warning("🔒 Identity Verification Required")
    col1, col2 = st.columns([3, 1])
    with col1:
        with st.form("verification_form"):
            auth_uid = st.text_input("User ID", placeholder="e.g. U1002").strip()
            auth_pin = st.text_input("4-digit PIN", type="password").strip()
            submit_btn = st.form_submit_button("Verify & Proceed")

            if submit_btn:
                if not auth_uid or not auth_pin:
                    st.error("Please enter both User ID and PIN.")
                else:
                    state["auth_user_id"] = auth_uid
                    state["auth_pin"] = auth_pin
                    state["turn"] += 1
                    try:
                        with st.spinner("Verifying..."):
                            LOGGER.info("streamlit_auth_start", extra={"turn": state["turn"]})
                            state = st.session_state.graph_app.invoke(state)
                        persist_turn(state, "[Authenticated]")
                        st.session_state.state = state
                        # Sync Streamlit display history
                        st.session_state.display_history.append(("user", "[Authenticated]"))
                        st.session_state.display_history.append(("assistant", state["reply"]))
                        st.rerun()
                    except MissingAPIKeyError as exc:
                        st.error("Missing LLM configuration.")
                        st.stop()
                    except Exception as exc:
                        st.error(f"Verification failed: {exc}")
    with col2:
        if st.button("Cancel Verification", use_container_width=True):
            state["intent"] = None
            st.session_state.state = state
            st.rerun()

else:
    user_input = st.chat_input("Type your message...")
    if user_input:
        st.session_state.display_history.append(("user", user_input))
        with st.chat_message("user"):
            st.write(user_input)

        state["turn"] += 1
        state["messages"].append({"role": "user", "content": user_input})
        state["reply"] = None

        try:
            with st.spinner("Thinking..."):
                LOGGER.info("streamlit_turn_start", extra={"turn": state["turn"]})
                state = st.session_state.graph_app.invoke(state)
            persist_turn(state, user_input)
            # Sync Streamlit display history
            if state.get("reply"):
                st.session_state.display_history.append(("assistant", state["reply"]))
            st.session_state.state = state
            LOGGER.info("streamlit_turn_complete", extra={"turn": state["turn"]})
            st.rerun()
        except MissingAPIKeyError as exc:
            LOGGER.warning("streamlit_missing_api_key")
            st.error("Missing LLM configuration.")
            st.info(str(exc))
            st.stop()
        except Exception:
            LOGGER.exception("streamlit_turn_failed")
            state["reply"] = "Sorry, something went wrong while processing that request."
            st.session_state.state = state
            st.rerun()

