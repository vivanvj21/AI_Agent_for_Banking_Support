"""
Phase 8 — Agent Capability Registry.

Every agent self-describes its capabilities here.
The intelligent supervisor uses this registry to make routing decisions
with confidence scoring rather than simple keyword-to-route mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentCapability:
    """Descriptor for what an agent can handle."""

    name: str  # routing name ("search", "account", etc.)
    display_name: str  # human-readable
    description: str  # what this agent does
    supported_intents: list[str]  # primary intent labels it handles
    supported_tools: list[str]  # tool names it can call
    requires_verification: bool = False  # True if user must be authenticated
    priority: int = 5  # 1=highest, 10=lowest (used to break ties)
    base_confidence: float = 0.8  # default confidence when this agent matches
    keywords: list[str] = field(default_factory=list)  # fast pre-filter hints
    examples: list[str] = field(default_factory=list)  # few-shot routing hints

    def matches_intent(self, intent: str) -> bool:
        return intent in self.supported_intents

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "supported_intents": self.supported_intents,
            "supported_tools": self.supported_tools,
            "requires_verification": self.requires_verification,
            "priority": self.priority,
            "base_confidence": self.base_confidence,
        }


# ── Registry entries ──────────────────────────────────────────────────────────

SEARCH_AGENT = AgentCapability(
    name="search",
    display_name="FAQ & Policy Search Agent",
    description=(
        "Answers general banking policy questions, FAQs about account types, "
        "interest rates, lost/stolen card procedures, and fraud reporting processes. "
        "Uses RAG over bank knowledge base. No user authentication required."
    ),
    supported_intents=["search"],
    supported_tools=["search_faq"],
    requires_verification=False,
    priority=3,
    base_confidence=0.85,
    keywords=[
        "what",
        "how",
        "policy",
        "procedure",
        "interest rate",
        "fee",
        "charge",
        "lost card",
        "stolen",
        "procedure",
        "general",
        "information",
        "tell me",
        "explain",
        "what happens",
        "can i",
        "is it possible",
    ],
    examples=[
        "What happens if I lose my card?",
        "What is the interest rate on savings accounts?",
        "How do I report fraud?",
        "What are the account types?",
    ],
)

ACCOUNT_AGENT = AgentCapability(
    name="account",
    display_name="Account Information Agent",
    description=(
        "Retrieves account balances, transaction history, and account details "
        "for the authenticated user. Also can recall previous session context. "
        "Requires identity verification."
    ),
    supported_intents=["account"],
    supported_tools=[
        "get_balance",
        "get_transaction_history",
        "recall_previous_session",
    ],
    requires_verification=True,
    priority=2,
    base_confidence=0.88,
    keywords=[
        "balance",
        "account",
        "transaction",
        "history",
        "statement",
        "amount",
        "money",
        "funds",
        "spending",
        "charges",
        "deposit",
        "withdrawal",
        "how much",
        "what's my",
        "show me",
        "previous",
        "last time",
    ],
    examples=[
        "What's my account balance?",
        "Show me my recent transactions",
        "What did I spend last month?",
        "Check my savings account",
    ],
)

FRAUD_AGENT = AgentCapability(
    name="fraud",
    display_name="Fraud & Security Agent",
    description=(
        "Handles security-sensitive actions: locking/unlocking cards, reporting "
        "cards lost or stolen, flagging fraudulent transactions, and viewing "
        "flagged transactions. Requires identity verification."
    ),
    supported_intents=["fraud"],
    supported_tools=[
        "lock_card",
        "unlock_card",
        "report_card_lost",
        "report_fraud_transaction",
        "get_flagged_transactions",
    ],
    requires_verification=True,
    priority=1,  # highest — fraud is time-sensitive
    base_confidence=0.90,
    keywords=[
        "lock",
        "unlock",
        "freeze",
        "block",
        "lost",
        "stolen",
        "fraud",
        "suspicious",
        "flag",
        "report",
        "unauthorized",
        "dispute",
        "security",
        "compromised",
        "stolen card",
        "fraudulent",
    ],
    examples=[
        "Lock my card immediately",
        "My card was stolen",
        "Report this transaction as fraud",
        "Flag transaction T900001",
        "Show my flagged transactions",
    ],
)

# Ordered registry: entries are tried in priority order
AGENT_REGISTRY: list[AgentCapability] = sorted(
    [SEARCH_AGENT, ACCOUNT_AGENT, FRAUD_AGENT],
    key=lambda a: a.priority,
)


def get_agent(name: str) -> AgentCapability | None:
    """Look up an agent capability by name."""
    return next((a for a in AGENT_REGISTRY if a.name == name), None)


def get_agents_for_intent(intent: str) -> list[AgentCapability]:
    """Return all agents that support a given intent, priority-ordered."""
    return [a for a in AGENT_REGISTRY if a.matches_intent(intent)]


def get_registry_description() -> str:
    """Render registry as a text block for use in supervisor prompts."""
    lines = ["Available agents:"]
    for agent in AGENT_REGISTRY:
        auth = " [requires authentication]" if agent.requires_verification else ""
        lines.append(f"  - {agent.name}: {agent.description[:120]}{auth}")
    return "\n".join(lines)
