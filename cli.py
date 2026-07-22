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

from __future__ import annotations

import argparse
import logging
import sys

from config import MissingAPIKeyError, validate_startup
from graph import build_graph, new_session_state, persist_turn, resume_session
from logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Bank Assistant CLI")
    parser.add_argument("--resume", help="Resume a persisted session by session_id")
    parser.add_argument(
        "--check-startup",
        action="store_true",
        help="Validate database, Chroma, memory, graph imports, and configuration, then exit.",
    )
    return parser.parse_args()


def _print_tool_log(state: dict) -> None:
    if not state.get("tool_calls_log"):
        print("  No tool calls recorded yet.")
        return
    for entry in state["tool_calls_log"]:
        print(
            f"  [{entry['turn']}] {entry['agent']} -> "
            f"{entry['tool']}({entry['args']}) => {entry['result_summary']}"
        )


def main() -> int:
    configure_logging()
    args = _parse_args()

    print("=" * 60)
    print("  Autonomous Bank Assistant (CLI demo)")
    print("  Type 'exit' to quit. Type 'log' to see the tool-call log.")
    print("=" * 60)

    startup = validate_startup(require_llm=not args.check_startup, initialize=True)
    if not startup.ok:
        print("\nConfiguration problem:")
        print(f"  {startup.message}")
        print(
            "\nFix the configuration and run again. No stack trace was shown to protect users."
        )
        return 2
    if args.check_startup:
        print("Startup validation passed.")
        for name, status in startup.details.items():
            print(f"  {name}: {status}")
        return 0

    try:
        app = build_graph()
        if args.resume:
            state = resume_session(args.resume)
            print(
                f"  Resumed session {state['session_id']} ({state['turn']} prior turn(s))."
            )
        else:
            state = new_session_state()
            print(f"  New session: {state['session_id']}")
            print(
                f"  (Reconnect later with: python cli.py --resume {state['session_id']})"
            )
    except Exception as exc:
        LOGGER.exception("cli_startup_failed")
        print("\nStartup failed while preparing the assistant session.")
        print(f"  {exc}")
        return 2

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            LOGGER.info("cli_shutdown")
            print("\nGoodbye.")
            return 0

        if user_input.lower() in ("exit", "quit"):
            LOGGER.info("cli_shutdown")
            print("Goodbye.")
            return 0
        if user_input.lower() == "log":
            _print_tool_log(state)
            continue
        if not user_input:
            print("Please enter a question or type 'exit' to quit.")
            continue

        try:
            state["turn"] += 1
            state["messages"].append({"role": "user", "content": user_input})
            state["reply"] = None

            LOGGER.info("cli_turn_start", extra={"turn": state["turn"]})
            state = app.invoke(state)
            persist_turn(state, user_input)
            LOGGER.info("cli_turn_complete", extra={"turn": state["turn"]})
        except MissingAPIKeyError as exc:
            LOGGER.warning("cli_missing_api_key")
            print(f"\nConfiguration problem: {exc}")
            return 2
        except Exception:
            LOGGER.exception("cli_turn_failed")
            print(
                "\nAssistant: Sorry, something went wrong while processing that request."
            )
            print("Please try again or contact support if the problem continues.")
            continue

        print(f"\nAssistant: {state['reply']}")

        if state.get("end_session"):
            print("\n[Session ended by assistant.]")
            return 0


if __name__ == "__main__":
    sys.exit(main())
