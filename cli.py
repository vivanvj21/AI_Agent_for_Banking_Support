"""
Console front-end for the Autonomous Bank Assistant.

Run: python cli.py

Try:
  "What happens if I lose my card?"                (search agent, no auth needed)
  "What's my balance? U1002, 1222"                  (account agent, inline demo auth)
  "Lock my card C3001. U1002, 1222"                 (fraud agent, inline demo auth)

Demo users are listed in db/seed_synthetic_data.py output (U1001..U1008 with
PINs 1111, 1222, 1333, ...).

Sessions are persisted (db/bank.db) as they happen. Run with
--resume <session_id> to continue a previous conversation after a restart.
"""

import sys
from graph import build_graph, new_session_state, resume_session, persist_turn


def main():
    print("=" * 60)
    print("  Autonomous Bank Assistant (CLI demo)")
    print("  Type 'exit' to quit. Type 'log' to see the tool-call log.")
    print("=" * 60)

    app = build_graph()

    if "--resume" in sys.argv:
        idx = sys.argv.index("--resume")
        session_id = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        state = resume_session(session_id) if session_id else new_session_state()
        print(f"  Resumed session {state['session_id']} ({state['turn']} prior turn(s)).")
    else:
        state = new_session_state()
        print(f"  New session: {state['session_id']}")
        print(f"  (Reconnect later with: python cli.py --resume {state['session_id']})")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            sys.exit(0)

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break
        if user_input.lower() == "log":
            for entry in state["tool_calls_log"]:
                print(f"  [{entry['turn']}] {entry['agent']} -> {entry['tool']}({entry['args']}) => {entry['result_summary']}")
            continue
        if not user_input:
            continue

        state["turn"] += 1
        state["messages"].append({"role": "user", "content": user_input})
        state["reply"] = None

        state = app.invoke(state)
        persist_turn(state, user_input)

        print(f"\nAssistant: {state['reply']}")

        if state.get("end_session"):
            print("\n[Session ended by assistant.]")
            break


if __name__ == "__main__":
    main()
