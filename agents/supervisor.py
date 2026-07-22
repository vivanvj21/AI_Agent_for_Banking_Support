"""
Supervisor: classifies user intent into one of {search, account, fraud,
unclear} and routes accordingly. Uses the LLM (ReAct-style reasoning, but
constrained to a single classification decision, not free tool use) rather
than keyword matching, so it generalizes past exact phrases like "loan" or
"balance" appearing literally in the text.

The supervisor itself never calls account/fraud tools — that separation is
what makes the blast-radius argument in the README defensible: even if the
supervisor's classification is compromised, it has no tools to abuse.
"""

import json
from anthropic import Anthropic
from config import require_llm_config

_anthropic_client = None


def get_client():
    """Create the Anthropic client lazily after config validation."""
    global _anthropic_client
    if _anthropic_client is None:
        config = require_llm_config()
        _anthropic_client = Anthropic(api_key=config.api_key)
    return _anthropic_client


SYSTEM_PROMPT = """You are a routing classifier for a bank customer support system.
Classify the user's message into exactly one category:

- "search": general questions about policies, account types, interest rates,
  fraud reporting process, or lost/stolen card procedures (no specific
  account data needed).
- "account": requests to check a balance, view transaction history, or other
  read-only requests about the user's own accounts.
- "fraud": requests to lock/unlock a card, report a card lost or stolen,
  report a transaction as fraud, or view previously flagged transactions.
- "unclear": greetings, small talk, or anything that doesn't clearly fit
  the above.

Respond with ONLY a JSON object: {"intent": "<one of the four categories>"}
No other text.
"""


def classify_intent(user_message: str) -> str:
    response = get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=50,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    try:
        parsed = json.loads(text)
        intent = parsed.get("intent", "unclear")
        if intent not in ("search", "account", "fraud", "unclear"):
            return "unclear"
        return intent
    except (json.JSONDecodeError, AttributeError):
        return "unclear"
