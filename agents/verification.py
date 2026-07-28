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
    Deprecated: Free-text credential extraction is disabled for security.
    Credentials must be provided via structured inputs.
    """
    return None, None


def try_verify(
    user_message: str | None = None,
    user_id: str | None = None,
    pin: str | None = None,
) -> dict:
    """
    Attempt to verify identity using structured user_id and pin.
    Returns:
      {"verified": True, "user_id": "..."} on success
      {"verified": False, "error": "..."} on failure or missing info
    """
    if not user_id or not pin:
        return {
            "verified": False,
            "error": "To access account or security actions, please verify your identity.",
        }
    result = verify_identity(user_id, pin)
    return result

