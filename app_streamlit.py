"""
Streamlit chat front-end for the Autonomous Bank Assistant.

Run: streamlit run app_streamlit.py

Demo users (see db/seed_synthetic_data.py): U1001..U1008, PINs 1111, 1222, ...
"""

import streamlit as st
from graph import build_graph, new_session_state, resume_session, persist_turn

st.set_page_config(page_title="Autonomous Bank Assistant", page_icon="🏦")
st.title("🏦 Autonomous Bank Assistant")
st.caption(
    "Demo agent — try: *\"What happens if I lose my card?\"* or "
    "*\"What's my balance? U1002, 1222\"*"
)

# Persist the session_id in the URL's query params so a browser refresh (or
# Streamlit process restart) reconnects to the same conversation instead of
# starting over -- ?sid=<session_id>.
query_sid = st.query_params.get("sid")

if "graph_app" not in st.session_state:
    st.session_state.graph_app = build_graph()
if "state" not in st.session_state:
    if query_sid:
        st.session_state.state = resume_session(query_sid)
    else:
        st.session_state.state = new_session_state(channel="streamlit")
    st.query_params["sid"] = st.session_state.state["session_id"]
if "display_history" not in st.session_state:
    # rebuild display history from persisted messages so a resumed session
    # shows its prior turns, not a blank chat window
    st.session_state.display_history = [
        (m["role"] if m["role"] == "user" else "assistant", m["content"])
        for m in st.session_state.state["messages"]
    ]

for role, content in st.session_state.display_history:
    with st.chat_message(role):
        st.write(content)

with st.sidebar:
    st.subheader("Session info")
    st.write("Session ID:", st.session_state.state.get("session_id"))
    st.write("Verified:", st.session_state.state.get("verified"))
    st.write("User ID:", st.session_state.state.get("user_id"))
    st.write("Turn:", st.session_state.state.get("turn"))
    st.caption("This conversation is saved automatically -- refreshing the page will reconnect to it.")
    if st.button("Show tool-call log"):
        for entry in st.session_state.state["tool_calls_log"]:
            st.code(f"[{entry['turn']}] {entry['agent']} -> {entry['tool']}({entry['args']})\n=> {entry['result_summary']}")
    if st.button("Start new session"):
        st.session_state.state = new_session_state(channel="streamlit")
        st.session_state.display_history = []
        st.query_params["sid"] = st.session_state.state["session_id"]
        st.rerun()

user_input = st.chat_input("Type your message...")
if user_input:
    st.session_state.display_history.append(("user", user_input))
    with st.chat_message("user"):
        st.write(user_input)

    state = st.session_state.state
    state["turn"] += 1
    state["messages"].append({"role": "user", "content": user_input})
    state["reply"] = None

    with st.spinner("Thinking..."):
        state = st.session_state.graph_app.invoke(state)
    persist_turn(state, user_input)
    st.session_state.state = state

    with st.chat_message("assistant"):
        st.write(state["reply"])
    st.session_state.display_history.append(("assistant", state["reply"]))

    if state.get("end_session"):
        st.warning("Session ended by assistant.")
