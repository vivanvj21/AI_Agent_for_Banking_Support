"""
Phase 8 — Orchestration Configuration.

Configuration-driven routing: thresholds, fallback rules, agent
preferences, and context limits. All values can be overridden via
environment variables for deployment-time tuning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class OrchestrationConfig:
    # ── Confidence thresholds ───────────────────────────────────────────────
    high_confidence_threshold: float = 0.75
    medium_confidence_threshold: float = 0.50
    low_confidence_threshold: float = 0.30
    fallback_threshold: float = 0.20  # below this → clarify

    # ── Routing ─────────────────────────────────────────────────────────────
    max_fallback_attempts: int = 2  # how many times to retry with next agent
    preferred_fallback_agent: str = "search"  # last-resort fallback
    enable_multi_agent_collab: bool = True  # allow agent-to-agent assistance

    # ── Context limits ───────────────────────────────────────────────────────
    max_context_tokens: int = 3000
    max_conversation_history_turns: int = 10
    max_rag_chunks: int = 5
    max_memory_facts: int = 8

    # ── Supervisor ───────────────────────────────────────────────────────────
    supervisor_model: str = "claude-haiku-4-5"  # cheap — just classification
    supervisor_max_tokens: int = 120

    # ── Collaboration ────────────────────────────────────────────────────────
    collab_trigger_keywords: list[str] = field(
        default_factory=lambda: [
            "also",
            "and also",
            "additionally",
            "plus",
            "in addition",
            "as well as",
            "together with",
        ]
    )

    # ── Fallback rules (intent → preferred fallback agent) ───────────────────
    fallback_rules: dict[str, str] = field(
        default_factory=lambda: {
            "account": "search",  # if account agent fails, try FAQ search
            "fraud": "search",  # if fraud agent fails, try FAQ
            "search": "clarify",  # if search fails, ask user to clarify
            "unclear": "clarify",
        }
    )


def get_orchestration_config() -> OrchestrationConfig:
    """Build config from central settings."""
    from config import settings
    orch = settings.orchestration
    return OrchestrationConfig(
        high_confidence_threshold=orch.high_confidence_threshold,
        medium_confidence_threshold=orch.medium_confidence_threshold,
        low_confidence_threshold=orch.low_confidence_threshold,
        fallback_threshold=orch.fallback_threshold,
        max_fallback_attempts=orch.max_fallback_attempts,
        enable_multi_agent_collab=orch.enable_multi_agent_collab,
        max_context_tokens=orch.max_context_tokens,
        max_conversation_history_turns=orch.max_history_turns,
        max_rag_chunks=orch.max_rag_chunks,
        max_memory_facts=orch.max_memory_facts,
        supervisor_model=orch.supervisor_model,
    )


# Module-level singleton
_config: OrchestrationConfig | None = None


def config() -> OrchestrationConfig:
    global _config
    if _config is None:
        _config = get_orchestration_config()
    return _config
