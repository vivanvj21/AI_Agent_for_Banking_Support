"""
Phase 8 — Confidence Scoring for routing decisions.

Rather than hard binary routing (account | fraud | search | unclear),
the intelligent supervisor now assigns a confidence score (0-1) to each
possible agent, and the routing logic picks the best one — or triggers
fallback if confidence is too low.
"""

from __future__ import annotations

from dataclasses import dataclass

from agents.registry import AGENT_REGISTRY, AgentCapability, get_agent

# ── Confidence tiers ──────────────────────────────────────────────────────────

HIGH_CONFIDENCE = 0.75  # route directly, no hesitation
MEDIUM_CONFIDENCE = 0.50  # route but flag for possible fallback
LOW_CONFIDENCE = 0.30  # try but be ready to escalate
FALLBACK_THRESHOLD = 0.20  # below this → clarify or human handoff


@dataclass
class RoutingDecision:
    """Result of the confidence-based routing step."""

    intent: str  # primary classified intent
    agent_name: str  # target agent name
    confidence: float  # 0–1 composite confidence
    tier: str  # "high" | "medium" | "low" | "fallback"
    fallback_agents: list[str]  # ordered backup agents
    reasoning: str  # brief explanation (logged, not shown to user)
    requires_verification: bool = False

    @property
    def is_high(self) -> bool:
        return self.confidence >= HIGH_CONFIDENCE

    @property
    def is_routable(self) -> bool:
        return self.confidence >= FALLBACK_THRESHOLD

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "agent_name": self.agent_name,
            "confidence": round(self.confidence, 3),
            "tier": self.tier,
            "fallback_agents": self.fallback_agents,
            "reasoning": self.reasoning,
            "requires_verification": self.requires_verification,
        }


def _tier(score: float) -> str:
    if score >= HIGH_CONFIDENCE:
        return "high"
    if score >= MEDIUM_CONFIDENCE:
        return "medium"
    if score >= LOW_CONFIDENCE:
        return "low"
    return "fallback"


def keyword_confidence(message: str, agent: AgentCapability) -> float:
    """
    Keyword overlap score between message and agent's keyword list.
    Returns 0–1; used as a fast pre-filter signal (not the only signal).
    """
    if not agent.keywords:
        return 0.0
    msg_lower = message.lower()
    hits = sum(1 for kw in agent.keywords if kw in msg_lower)
    return min(1.0, hits / max(3, len(agent.keywords) * 0.3))


def length_confidence_boost(message: str) -> float:
    """
    Longer, more specific messages tend to be higher confidence.
    Very short messages (< 5 words) get a small penalty.
    """
    words = len(message.split())
    if words < 3:
        return -0.10
    if words < 6:
        return 0.0
    return min(0.10, (words - 6) * 0.01)


def context_confidence_boost(
    intent: str,
    recent_intents: list[str],
    verified: bool,
) -> float:
    """
    Boost confidence if the current intent is consistent with recent intents
    (conversation has established a topic) or if user is already verified.
    """
    boost = 0.0
    if recent_intents and intent in recent_intents[-3:]:
        boost += 0.08  # same intent as recent turns
    if verified and intent in ("account", "fraud"):
        boost += 0.05  # already authenticated, less friction
    return boost


def compute_routing_decision(
    intent: str,
    message: str,
    recent_intents: list[str] | None = None,
    verified: bool = False,
) -> RoutingDecision:
    """
    Compute a RoutingDecision for the given intent and message.

    Algorithm:
    1. Find agent(s) that support the intent.
    2. Start with the agent's base_confidence.
    3. Apply keyword overlap signal.
    4. Apply message length boost.
    5. Apply conversation context boost.
    6. Clamp to [0, 1].
    7. Build fallback list from remaining agents.
    """
    recent = recent_intents or []
    candidates = [a for a in AGENT_REGISTRY if a.matches_intent(intent)]

    if not candidates:
        # No agent handles this intent — route to clarify
        return RoutingDecision(
            intent=intent,
            agent_name="clarify",
            confidence=0.0,
            tier="fallback",
            fallback_agents=[],
            reasoning=f"No agent registered for intent={intent!r}",
        )

    # Score each candidate
    scored: list[tuple[float, AgentCapability]] = []
    for agent in candidates:
        score = agent.base_confidence
        kw = keyword_confidence(message, agent)
        score += kw * 0.15
        score += length_confidence_boost(message)
        score += context_confidence_boost(intent, recent, verified)
        score = max(0.0, min(1.0, score))
        scored.append((score, agent))

    scored.sort(key=lambda x: -x[0])
    best_score, best_agent = scored[0]

    # Build fallbacks from other scoring candidates + agents with different intent
    fallbacks = [a.name for _, a in scored[1:]]
    # Add search as universal fallback if not already primary
    if best_agent.name != "search" and "search" not in fallbacks:
        fallbacks.append("search")

    reasoning = (
        f"intent={intent!r}, agent={best_agent.name!r}, "
        f"base={best_agent.base_confidence:.2f}, "
        f"kw_signal={keyword_confidence(message, best_agent):.2f}, "
        f"verified={verified}"
    )

    return RoutingDecision(
        intent=intent,
        agent_name=best_agent.name,
        confidence=best_score,
        tier=_tier(best_score),
        fallback_agents=fallbacks,
        reasoning=reasoning,
        requires_verification=best_agent.requires_verification,
    )


def get_fallback_decision(
    failed_agent: str,
    original_decision: RoutingDecision,
    message: str,
) -> RoutingDecision | None:
    """
    Called when the primary agent returns a 'can't handle' signal.
    Returns the next best routing decision, or None if no fallback.
    """
    for fb_name in original_decision.fallback_agents:
        agent = get_agent(fb_name)
        if agent and agent.name != failed_agent:
            return RoutingDecision(
                intent=original_decision.intent,
                agent_name=agent.name,
                confidence=max(0.0, original_decision.confidence - 0.20),
                tier="low",
                fallback_agents=[
                    f for f in original_decision.fallback_agents if f != fb_name
                ],
                reasoning=f"Fallback from {failed_agent!r} → {agent.name!r}",
                requires_verification=agent.requires_verification,
            )
    return None
