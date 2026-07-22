"""
Identity verification node. Deliberately NOT an LLM-callable tool — this is a
plain Python function invoked as a hard graph edge before Account/Fraud
agents. This is the answer to "how do you stop a prompt injection from
talking its way past identity checks": the check is in code, not in a system
prompt the model could be argued out of.

The CLI/front-end is responsible for collecting user_id + PIN once per
session and passing them into the graph state; this module only checks them.
"""

import re
from tools.account_tools import verify_identity


def extract_credentials(user_message: str) -> tuple[str | None, str | None]:
    """
    Very small heuristic extractor for the demo CLI: looks for patterns like
    'U1002' and a standalone 4-digit PIN in the message. In a real product,
    this would be a structured login form, not free-text parsing — free-text
    credential parsing is a demo convenience only.
    """
    user_id_match = re.search(r"\bU\d{4}\b", user_message)
    pin_match = re.search(r"\b\d{4}\b", user_message.replace(user_id_match.group() if user_id_match else "", ""))
    user_id = user_id_match.group() if user_id_match else None
    pin = pin_match.group() if pin_match else None
    return user_id, pin


def try_verify(user_message: str) -> dict:
    """
    Attempt to verify identity from free text. Returns:
      {"verified": True, "user_id": "..."} on success
      {"verified": False, "error": "..."} on failure or missing info
    """
    user_id, pin = extract_credentials(user_message)
    if not user_id or not pin:
        return {
            "verified": False,
            "error": "To access account or security actions, please provide your user ID and 4-digit PIN, e.g. 'U1002, 1222'.",
        }
    result = verify_identity(user_id, pin)
    return result
