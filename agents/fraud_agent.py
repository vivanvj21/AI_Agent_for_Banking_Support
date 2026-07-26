"""
Fraud Agent: state-changing security actions (lock card, report lost/stolen,
flag a transaction as fraud). Only invoked after verification.

Design choice: this agent's tools are all naturally idempotent/reversible
except report_card_lost, which the system prompt is instructed to confirm
before calling. We don't hard-block it in code the way we hard-block identity
verification, because "confirm before an irreversible action" is a
reasonable place to trust a well-prompted LLM — unlike identity verification,
getting this wrong once just means an extra confirmation round-trip, not a
data leak.
"""

from anthropic import Anthropic

from config import require_llm_config
from tools.fraud_tools import (
    get_flagged_transactions,
    lock_card,
    report_card_lost,
    report_fraud_transaction,
    unlock_card,
)

_anthropic_client = None


def get_client():
    """Create the Anthropic client lazily after config validation."""
    global _anthropic_client
    if _anthropic_client is None:
        config = require_llm_config()
        _anthropic_client = Anthropic(api_key=config.api_key)
    return _anthropic_client


TOOLS = [
    {
        "name": "lock_card",
        "description": "Instantly lock a card belonging to the verified user. Reversible — can be unlocked later.",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string", "description": "Card ID, e.g. 'C3001'."}
            },
            "required": ["card_id"],
        },
    },
    {
        "name": "unlock_card",
        "description": "Unlock a previously locked card belonging to the verified user.",
        "input_schema": {
            "type": "object",
            "properties": {"card_id": {"type": "string"}},
            "required": ["card_id"],
        },
    },
    {
        "name": "report_card_lost",
        "description": "Permanently report a card lost/stolen and trigger replacement. NOT reversible — always confirm with the user before calling this.",
        "input_schema": {
            "type": "object",
            "properties": {"card_id": {"type": "string"}},
            "required": ["card_id"],
        },
    },
    {
        "name": "report_fraud_transaction",
        "description": "Flag a specific transaction as fraudulent for investigation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string"},
                "reason": {
                    "type": "string",
                    "description": "Brief reason the transaction looks fraudulent.",
                },
            },
            "required": ["transaction_id"],
        },
    },
    {
        "name": "get_flagged_transactions",
        "description": "List all transactions currently flagged as fraud for the verified user.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

SYSTEM_PROMPT = """You are the Fraud & Security Agent for a bank's customer support system.
The user has already been identity-verified.

You can lock/unlock cards, report a card lost/stolen, flag transactions as
fraud, and list previously flagged transactions.

Rules:
- report_card_lost is PERMANENT (triggers a replacement card and cannot be
  undone). Before calling it, explicitly confirm with the user in your reply
  that they want to proceed — do not call it on the first mention of a lost
  card. Suggest lock_card first as the safer, reversible option if the card
  might just be misplaced.
- lock_card, unlock_card, and report_fraud_transaction are safe to call
  directly when the user's intent is clear.
- Always call the appropriate tool rather than claiming an action succeeded
  without calling it.
- Keep responses concise and reassuring — the user may be anxious about fraud.
"""


def run_fraud_agent(
    user_message: str,
    user_id: str,
    tool_log: list,
    turn: int,
    max_tool_iters: int = 3,
    system_prompt_override: str | None = None,
) -> str:
    effective_prompt = system_prompt_override or SYSTEM_PROMPT
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_tool_iters):
        response = get_client().messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=effective_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks).strip() or "I couldn't process that request."

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            args = dict(block.input)
            args["user_id"] = (
                user_id  # server-injected, never trust LLM-supplied user_id
            )

            fn_map = {
                "lock_card": lock_card,
                "unlock_card": unlock_card,
                "report_card_lost": report_card_lost,
                "report_fraud_transaction": report_fraud_transaction,
                "get_flagged_transactions": get_flagged_transactions,
            }
            fn = fn_map.get(block.name)
            result = fn(**args) if fn else {"error": f"Unknown tool {block.name}"}

            tool_log.append(
                {
                    "turn": turn,
                    "agent": "fraud_agent",
                    "tool": block.name,
                    "args": block.input,
                    "result_summary": str(result)[:120],
                }
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "I'm having trouble completing that action right now — for your safety, please contact support directly."
