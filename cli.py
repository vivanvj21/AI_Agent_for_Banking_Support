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
    # ── RAGAS evaluation ────────────────────────────────────────────────────
    parser.add_argument(
        "--evaluate-rag",
        metavar="DATASET",
        help=(
            "Evaluate RAG quality using RAGAS. "
            "DATASET is a path to a JSONL / JSON / CSV file "
            "or a LangSmith dataset name prefixed with 'langsmith:'. "
            "Example: python cli.py --evaluate-rag eval_data.jsonl"
        ),
    )
    parser.add_argument(
        "--eval-output",
        metavar="DIR",
        default=None,
        help="Directory for evaluation reports (default: EVAL_OUTPUT_DIR env var or 'evaluation_reports').",
    )
    parser.add_argument(
        "--eval-metrics",
        metavar="METRICS",
        default=None,
        help="Comma-separated RAGAS metrics to compute (default: all four).",
    )
    return parser.parse_args()


def _run_evaluation(args: argparse.Namespace) -> int:
    """Run RAGAS evaluation and print results.  Returns an exit code."""
    import os
    import time

    from evaluation import get_eval_config, ragas_available
    from evaluation.dataset_loader import load_dataset, load_from_langsmith
    from evaluation.ragas_runner import RagasRunner

    if not ragas_available():
        print(
            "\nRAGAS is not installed. Run:\n"
            "  pip install ragas langchain-anthropic\n"
            "Then set ANTHROPIC_API_KEY and re-run."
        )
        return 2

    # Apply CLI overrides to environment before building config
    if args.eval_output:
        os.environ["EVAL_OUTPUT_DIR"] = args.eval_output
    if args.eval_metrics:
        os.environ["EVAL_METRICS"] = args.eval_metrics

    config = get_eval_config()
    dataset_arg: str = args.evaluate_rag

    print("\n" + "=" * 60)
    print("  RAGAS Evaluation")
    print("=" * 60)
    print(f"  Dataset  : {dataset_arg}")
    print(f"  Model    : {config.eval_model}")
    print(f"  Metrics  : {', '.join(config.metrics)}")
    print(f"  Output   : {config.output_dir}")
    print("=" * 60 + "\n")

    # Load samples
    try:
        if dataset_arg.startswith("langsmith:"):
            dataset_name = dataset_arg[len("langsmith:") :]
            print(f"Loading from LangSmith dataset: {dataset_name}")
            samples = load_from_langsmith(dataset_name)
        else:
            print(f"Loading from file: {dataset_arg}")
            samples = load_dataset(dataset_arg)
    except FileNotFoundError:
        print(f"\nError: Dataset file not found: {dataset_arg}")
        return 2
    except ValueError as exc:
        print(f"\nError: {exc}")
        return 2

    if not samples:
        print("\nNo valid samples found in the dataset. Nothing to evaluate.")
        return 1

    print(f"Loaded {len(samples)} sample(s). Starting evaluation…\n")

    # Run evaluation
    try:
        t0 = time.perf_counter()
        runner = RagasRunner(config, dataset_name=dataset_arg)
        report = runner.evaluate(samples)
        elapsed = time.perf_counter() - t0
    except ImportError as exc:
        print(f"\nError: {exc}")
        return 2
    except RuntimeError as exc:
        print(f"\nEvaluation failed: {exc}")
        return 2

    # Print results
    print("=" * 60)
    print("  Results")
    print("=" * 60)
    for metric, score in report.aggregate_scores.items():
        bar = "█" * round(score * 20) + "░" * (20 - round(score * 20))
        print(f"  {metric:<22} {score:.4f}  {bar}")
    print("-" * 60)
    print(f"  Mean overall score   {report.mean_overall_score:.4f}")
    print(f"  Evaluated samples    {report.evaluated_samples}/{report.total_samples}")
    print(f"  Failed samples       {report.failed_samples}")
    print(f"  Elapsed              {elapsed:.2f}s")
    print("=" * 60 + "\n")

    # Save reports
    try:
        written = report.save(output_dir=config.output_dir, fmt="both")
        for fmt_name, path in written.items():
            print(f"  Saved {fmt_name} report: {path}")
    except Exception:
        LOGGER.debug("eval_report_save_failed", exc_info=True)
        print("  Warning: could not write report files.")

    return 0


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

    # ── RAGAS evaluation path (exits before the chat loop) ──────────────────
    if args.evaluate_rag:
        return _run_evaluation(args)

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
