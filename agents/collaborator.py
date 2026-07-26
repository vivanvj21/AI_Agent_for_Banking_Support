"""
Phase 8 — Multi-Agent Collaboration.

Allows an agent to request supplementary information from another agent
when a single agent cannot fully answer a request.

Example flows:
  Fraud query with account context needed:
    fraud_agent → requests account_agent for balance context
    → merges both results into a single response

  Account query with policy question embedded:
    account_agent → requests search_agent for policy text
    → appends policy answer to account response

This is invoked from the graph orchestrator (graph.py) when an agent
returns a NEEDS_COLLABORATION signal, or proactively when the supervisor
detects a multi-domain query (contains collab trigger keywords).
"""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)

# Sentinel that agents can return to signal they need help
NEEDS_COLLABORATION = "__NEEDS_COLLABORATION__"


def detect_collaboration_need(
    message: str,
    primary_intent: str,
    trigger_keywords: list[str],
) -> tuple[bool, list[str]]:
    """
    Detect if a message spans multiple agent domains.
    Returns (needs_collab, list_of_assisting_agents).
    """
    msg_lower = message.lower()

    # Check trigger keywords
    has_trigger = any(kw in msg_lower for kw in trigger_keywords)

    # Check for cross-domain signals
    assisting: list[str] = []

    if primary_intent in ("fraud", "account"):
        # A fraud/account query that also asks a policy question
        policy_signals = [
            "what is",
            "how does",
            "explain",
            "what are the rules",
            "policy",
        ]
        if any(s in msg_lower for s in policy_signals):
            assisting.append("search")

    if primary_intent == "fraud":
        # Fraud agent wanting to show the balance for context
        balance_signals = ["balance", "amount", "how much", "funds", "charged"]
        if any(s in msg_lower for s in balance_signals):
            assisting.append("account")

    needs_collab = bool(assisting) and has_trigger
    return needs_collab, assisting


def run_search_agent_assist(
    query: str,
    tool_log: list,
    turn: int,
) -> str:
    """Invoke search agent in assist mode (no full agent loop, just FAQ lookup)."""
    try:
        from tools.faq_search import search_faq

        result = search_faq(query, k=2)
        hits = result.get("results", [])
        if not hits:
            return ""
        tool_log.append(
            {
                "turn": turn,
                "agent": "collab:search",
                "tool": "search_faq",
                "args": {"query": query},
                "result_summary": f"{len(hits)} chunks",
            }
        )
        lines = []
        for hit in hits[:2]:
            citation = hit.get("citation", "faq")
            lines.append(f"[{citation}] {hit.get('text', '')[:200]}")
        return "\n".join(lines)
    except Exception as exc:
        LOGGER.warning("collab_search_failed", extra={"error": str(exc)})
        return ""


def run_account_agent_assist(
    user_id: str,
    query: str,
    tool_log: list,
    turn: int,
) -> str:
    """Invoke account tool in assist mode (just balance, no full agent loop)."""
    try:
        from tools.account_tools import get_balance

        result = get_balance(user_id)
        tool_log.append(
            {
                "turn": turn,
                "agent": "collab:account",
                "tool": "get_balance",
                "args": {},
                "result_summary": str(result)[:80],
            }
        )
        accounts = result.get("accounts", [])
        if not accounts:
            return ""
        lines = [
            f"Account {a.get('account_id')}: {a.get('currency', 'INR')} {a.get('balance', 0):,.2f}"
            for a in accounts[:3]
        ]
        return "Current balances:\n" + "\n".join(lines)
    except Exception as exc:
        LOGGER.warning("collab_account_failed", extra={"error": str(exc)})
        return ""


def build_collaboration_context(
    primary_result: str,
    assist_results: dict[str, str],
) -> str:
    """
    Merge primary agent result with assist results into a single coherent response.
    The assist results are appended as supplementary context.
    """
    if not assist_results:
        return primary_result

    parts = [primary_result]
    for agent_name, assist_text in assist_results.items():
        if assist_text:
            parts.append(f"\n[Additional context from {agent_name}]\n{assist_text}")

    return "\n".join(parts)


def collaborate(
    primary_intent: str,
    assisting_agents: list[str],
    user_message: str,
    user_id: str | None,
    primary_result: str,
    tool_log: list,
    turn: int,
) -> str:
    """
    Coordinate supplementary agent calls and merge results.
    Only called when collaboration is explicitly triggered.
    """
    assist_results: dict[str, str] = {}

    for agent_name in assisting_agents:
        if agent_name == "search":
            result = run_search_agent_assist(user_message, tool_log, turn)
            if result:
                assist_results["policy search"] = result

        elif agent_name == "account" and user_id:
            result = run_account_agent_assist(user_id, user_message, tool_log, turn)
            if result:
                assist_results["account info"] = result

    return build_collaboration_context(primary_result, assist_results)
