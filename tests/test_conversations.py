"""
Scripted-conversation evaluation harness. Requires ANTHROPIC_API_KEY (these
tests make real Claude API calls, unlike test_tools.py).

Run: python tests/test_conversations.py
(Not run via plain pytest by default, since it costs API credits and takes
longer — kept as a standalone script you run deliberately, e.g. before a
release, and wired into CI as an optional/manual job rather than on every push.)

Each case defines:
  - a scripted single-turn or multi-turn input
  - the expected intent the supervisor should pick
  - the expected tool(s) that should be called
  - a simple substring/structural check on the final reply

This gives concrete, computed numbers for:
  - Task Success Rate:   fraction of cases where the final state/reply matches expectations
  - Tool-Use Accuracy:   fraction of cases where the expected tool(s) were actually invoked
  - Latency:             wall-clock time per case, p50/p95 across the run
"""

import time
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph import build_graph, new_session_state


CASES = [
    {
        "name": "faq_lost_card",
        "turns": ["What happens if I lose my card?"],
        "expected_intent": "search",
        "expected_tools": {"search_faq"},
        "check": lambda reply: "lock" in reply.lower() or "report" in reply.lower(),
    },
    {
        "name": "faq_interest_rate",
        "turns": ["What's the interest rate on savings accounts?"],
        "expected_intent": "search",
        "expected_tools": {"search_faq"},
        "check": lambda reply: any(ch.isdigit() for ch in reply),
    },
    {
        "name": "balance_check_with_creds",
        "turns": ["What's my balance? U1002, 1222"],
        "expected_intent": "account",
        "expected_tools": {"get_balance"},
        "check": lambda reply: any(ch.isdigit() for ch in reply),
    },
    {
        "name": "balance_check_missing_creds",
        "turns": ["What's my balance?"],
        "expected_intent": "account",
        "expected_tools": set(),  # should NOT call any tool — must ask for credentials first
        "check": lambda reply: "pin" in reply.lower() or "user id" in reply.lower(),
    },
    {
        "name": "lock_card_with_creds",
        "turns": ["Please lock my card C3003. U1002, 1222"],
        "expected_intent": "fraud",
        "expected_tools": {"lock_card"},
        "check": lambda reply: "lock" in reply.lower(),
    },
    {
        "name": "wrong_pin_rejected",
        "turns": ["What's my balance? U1002, 9999"],
        "expected_intent": "account",
        "expected_tools": set(),
        "check": lambda reply: "match" in reply.lower() or "verify" in reply.lower() or "pin" in reply.lower(),
    },
    {
        "name": "greeting_clarify",
        "turns": ["hey"],
        "expected_intent": "unclear",
        "expected_tools": set(),
        "check": lambda reply: "help" in reply.lower(),
    },
]


def run_case(case):
    app = build_graph()
    state = new_session_state()

    start = time.time()
    for turn in case["turns"]:
        state["turn"] += 1
        state["messages"].append({"role": "user", "content": turn})
        state["reply"] = None
        state = app.invoke(state)
    elapsed = time.time() - start

    intent_ok = state.get("intent") == case["expected_intent"]
    called_tools = {entry["tool"] for entry in state["tool_calls_log"]}
    tools_ok = case["expected_tools"].issubset(called_tools) if case["expected_tools"] else len(called_tools) == 0
    reply_ok = case["check"](state.get("reply") or "")

    success = intent_ok and tools_ok and reply_ok

    return {
        "name": case["name"],
        "success": success,
        "intent_ok": intent_ok,
        "tools_ok": tools_ok,
        "reply_ok": reply_ok,
        "latency_s": round(elapsed, 2),
        "actual_intent": state.get("intent"),
        "actual_tools": list(called_tools),
        "reply": state.get("reply"),
    }


def main():
    results = [run_case(c) for c in CASES]

    n = len(results)
    success_rate = sum(r["success"] for r in results) / n
    tool_accuracy = sum(r["tools_ok"] for r in results) / n
    latencies = [r["latency_s"] for r in results]

    print(f"{'CASE':<28} {'SUCCESS':<8} {'INTENT':<8} {'TOOLS':<8} {'LATENCY(s)':<10}")
    for r in results:
        print(f"{r['name']:<28} {str(r['success']):<8} {str(r['intent_ok']):<8} {str(r['tools_ok']):<8} {r['latency_s']:<10}")
        if not r["success"]:
            print(f"    -> intent={r['actual_intent']} tools={r['actual_tools']} reply={r['reply']!r}")

    print("\n--- Summary ---")
    print(f"Task Success Rate: {success_rate:.0%} ({sum(r['success'] for r in results)}/{n})")
    print(f"Tool-Use Accuracy: {tool_accuracy:.0%} ({sum(r['tools_ok'] for r in results)}/{n})")
    print(f"Latency — p50: {statistics.median(latencies):.2f}s, "
          f"max: {max(latencies):.2f}s, mean: {statistics.mean(latencies):.2f}s")

    return results


if __name__ == "__main__":
    main()
