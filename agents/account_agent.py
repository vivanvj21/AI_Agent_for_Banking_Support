"""
Account Agent: read-mostly account data (balance, transaction history).
Only invoked after the graph's verification gate has set state["verified"] =
True — this agent trusts that user_id has already been authenticated, but
every tool call still re-checks row ownership in SQL as defense in depth.
"""

from anthropic import Anthropic

from config import require_llm_config
from tools.account_tools import get_balance, get_transaction_history
from tools.memory import get_last_session_summary_for_user

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
        "name": "get_balance",
        "description": "Get the balance for one account, or all accounts belonging to the verified user if account_id is omitted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "Specific account ID, e.g. 'A2001'. Omit to list all accounts.",
                },
            },
        },
    },
    {
        "name": "get_transaction_history",
        "description": "Get recent transactions for the verified user, optionally scoped to one account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "Specific account ID to filter by. Omit for all accounts.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of transactions to return.",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "recall_previous_session",
        "description": "Look up what the verified user talked to the assistant about in their most recent prior session (a different day/conversation than this one). Use this when the user references an earlier conversation, e.g. 'what did I ask about yesterday' or 'my previous issue'.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

SYSTEM_PROMPT = """You are the Account Agent for a bank's customer support system.
The user has already been identity-verified — you do NOT need to ask for a
PIN or user ID again this session.

You can look up account balances and transaction history using your tools.
Always call a tool rather than guessing numbers. Present amounts with the
account's currency. Keep answers concise and factual.

If the user references a previous conversation (e.g. "what did I ask about
last time", "my issue from yesterday"), use recall_previous_session rather
than guessing -- if it returns nothing, say you don't have a record of an
earlier session.

If the user asks to lock a card, report fraud, or anything involving taking
an action (not just looking something up), say that request will be handed
to the fraud/security team and should not be answered by you.
"""


def run_account_agent(
    user_message: str,
    user_id: str,
    tool_log: list,
    turn: int,
    max_tool_iters: int = 3,
    session_id: str | None = None,
) -> str:
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_tool_iters):
        response = get_client().messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=SYSTEM_PROMPT,
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
                user_id  # inject verified user_id server-side; never trust the LLM to supply it
            )

            if block.name == "get_balance":
                result = get_balance(**args)
            elif block.name == "get_transaction_history":
                result = get_transaction_history(**args)
            elif block.name == "recall_previous_session":
                summary = get_last_session_summary_for_user(
                    user_id, exclude_session_id=session_id
                )
                result = (
                    summary
                    if summary
                    else {"error": "No previous session found for this user."}
                )
            else:
                result = {"error": f"Unknown tool {block.name}"}

            tool_log.append(
                {
                    "turn": turn,
                    "agent": "account_agent",
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

    return "I'm having trouble completing that lookup right now — please try again shortly."
