"""
Phase 8 — Intelligent Supervisor.

Replaces the simple one-shot classify_intent() call with a full
confidence-based routing pipeline:

  1. Fast keyword pre-filter (zero LLM cost)
  2. LLM intent classification WITH confidence + reasoning
  3. Confidence score composition (LLM + keyword + context)
  4. RoutingDecision with fallback chain

The original classify_intent() is kept for backward compat.
The new entry point is classify_with_confidence().
"""

from __future__ import annotations

import json
import logging

from anthropic import Anthropic

from agents.confidence import (
    RoutingDecision,
    compute_routing_decision,
    keyword_confidence,
)
from agents.orchestration_config import config as orch_config
from agents.prompt_builder import build_supervisor_prompt
from agents.registry import AGENT_REGISTRY, get_registry_description
from config import require_llm_config

LOGGER = logging.getLogger(__name__)

_anthropic_client = None


def _get_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        cfg = require_llm_config()
        _anthropic_client = Anthropic(api_key=cfg.api_key)
    return _anthropic_client


# ── Fast keyword pre-filter ───────────────────────────────────────────────────


def _keyword_prefilter(message: str) -> str | None:
    """
    Zero-cost keyword scan before LLM call.
    Returns an intent if a strong keyword signal exists, else None.
    High threshold (0.4) so we only skip the LLM for very clear cases.
    """
    best_score = 0.0
    best_intent = None
    for agent in AGENT_REGISTRY:
        score = keyword_confidence(message, agent)
        if score > best_score:
            best_score = score
            best_intent = agent.name
    if best_score >= 0.45:
        LOGGER.debug(
            "supervisor_keyword_prefilter",
            extra={"intent": best_intent, "score": best_score},
        )
        return best_intent
    return None


# ── LLM classification ────────────────────────────────────────────────────────


def _llm_classify(
    message: str,
    conversation_history: list[dict] | None = None,
) -> tuple[str, float, str]:
    """
    Call the LLM supervisor to classify intent.
    Returns (intent, llm_confidence, reasoning).
    Uses claude-haiku (cheap) — classification needs no reasoning depth.
    """
    cfg = orch_config()
    system = build_supervisor_prompt(get_registry_description())

    # Include last 3 turns of conversation for context (cheap)
    messages: list[dict] = []
    if conversation_history:
        for msg in conversation_history[-3:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    try:
        response = _get_client().messages.create(
            model=cfg.supervisor_model,
            max_tokens=cfg.supervisor_max_tokens,
            system=system,
            messages=messages,
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        parsed = json.loads(text)
        intent = parsed.get("intent", "unclear")
        if intent not in ("search", "account", "fraud", "unclear"):
            intent = "unclear"
        llm_confidence = float(parsed.get("confidence", 0.5))
        reasoning = parsed.get("reasoning", "")
        return intent, llm_confidence, reasoning
    except Exception as exc:
        LOGGER.warning("supervisor_llm_failed", extra={"error": str(exc)})
        return "unclear", 0.3, f"LLM classification failed: {exc}"


# ── Composite confidence ──────────────────────────────────────────────────────


def _compose_confidence(
    llm_confidence: float,
    intent: str,
    message: str,
    recent_intents: list[str],
    verified: bool,
) -> float:
    """
    Blend LLM confidence with structural signals:
    - LLM confidence (weight 0.65): primary signal
    - Keyword overlap (weight 0.25): structural validation
    - Context boost (weight 0.10): conversation consistency
    """
    from agents.confidence import (
        context_confidence_boost,
        length_confidence_boost,
    )
    from agents.confidence import (
        keyword_confidence as kw_conf,
    )
    from agents.registry import get_agent

    agent = get_agent(intent)
    kw_score = kw_conf(message, agent) if agent else 0.0
    ctx_boost = context_confidence_boost(intent, recent_intents, verified)
    len_boost = length_confidence_boost(message)

    composite = 0.65 * llm_confidence + 0.25 * kw_score + 0.10 * (ctx_boost + len_boost)
    return max(0.0, min(1.0, composite))


# ── Public API ────────────────────────────────────────────────────────────────


def classify_with_confidence(
    message: str,
    conversation_history: list[dict] | None = None,
    recent_intents: list[str] | None = None,
    verified: bool = False,
    use_prefilter: bool = True,
) -> RoutingDecision:
    """
    Full intelligent routing pipeline.

    Steps:
    1. Keyword pre-filter (skip LLM for very obvious cases)
    2. LLM classification with confidence + reasoning
    3. Composite confidence blending
    4. RoutingDecision with fallback chain

    Args:
        message: latest user message
        conversation_history: [{role, content}] list
        recent_intents: list of intent strings from recent turns
        verified: whether the user is already authenticated
        use_prefilter: set False to always use the LLM

    Returns:
        RoutingDecision with agent_name, confidence, tier, fallbacks
    """
    recent = recent_intents or []

    # Step 1: Keyword pre-filter (zero LLM calls for obvious intents)
    if use_prefilter:
        prefilter_intent = _keyword_prefilter(message)
        if prefilter_intent and prefilter_intent != "unclear":
            # Compute decision without LLM for high-signal cases
            decision = compute_routing_decision(
                intent=prefilter_intent,
                message=message,
                recent_intents=recent,
                verified=verified,
            )
            # Only trust prefilter if confidence is HIGH
            if decision.is_high:
                LOGGER.info(
                    "supervisor_prefilter_routed",
                    extra={
                        "intent": prefilter_intent,
                        "confidence": decision.confidence,
                    },
                )
                return decision

    # Step 2: LLM classification
    intent, llm_confidence, reasoning = _llm_classify(message, conversation_history)

    # Step 3: Composite confidence
    composite_conf = _compose_confidence(
        llm_confidence, intent, message, recent, verified
    )

    # Step 4: Build routing decision
    decision = compute_routing_decision(
        intent=intent,
        message=message,
        recent_intents=recent,
        verified=verified,
    )
    # Override with composite confidence
    decision.confidence = composite_conf
    from agents.confidence import _tier

    decision.tier = _tier(composite_conf)
    decision.reasoning = f"{reasoning} | composite={composite_conf:.3f}"

    LOGGER.info(
        "supervisor_routing_decision",
        extra={
            "intent": intent,
            "agent": decision.agent_name,
            "confidence": composite_conf,
            "tier": decision.tier,
            "llm_conf": llm_confidence,
        },
    )
    return decision


def classify_intent(user_message: str) -> str:
    """
    Backward-compatible wrapper.
    Returns a bare intent string (search | account | fraud | unclear).
    New code should use classify_with_confidence() instead.
    """
    decision = classify_with_confidence(user_message)
    return decision.intent
