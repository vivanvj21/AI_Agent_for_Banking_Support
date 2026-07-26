"""
Memory Engine — configuration.

All tunable parameters live here so the rest of the engine never has
magic numbers inline.  Values default from environment variables so
they can be overridden without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class MemoryConfig:
    # ── Limits ──────────────────────────────────────────────────────────────
    max_conversation_turns: int = 50  # per session kept verbatim
    max_long_term_memories: int = 200  # per user in SQLite
    max_semantic_memories: int = 500  # per user in Chroma collection
    max_context_tokens: int = 4000  # soft cap for context builder

    # ── Retrieval ────────────────────────────────────────────────────────────
    similarity_threshold: float = 0.35  # min cosine similarity for semantic hits
    top_k_semantic: int = 5  # max semantic results to return
    top_k_recency: int = 10  # max recency-sorted results
    top_k_context: int = 8  # max memories merged into final context

    # ── Summarisation ────────────────────────────────────────────────────────
    summary_threshold_turns: int = 20  # summarise when session > N turns
    summary_max_tokens: int = 600  # max size of a session summary

    # ── Ranking weights ──────────────────────────────────────────────────────
    importance_weight: float = 0.4
    recency_weight: float = 0.3
    relevance_weight: float = 0.3

    # ── Expiration / TTL ─────────────────────────────────────────────────────
    session_ttl_days: int = 90  # sessions deleted after N days idle
    long_term_ttl_days: int = 365  # long-term memories expire after 1 year
    conversation_ttl_days: int = 30  # conversation turns expire after 30 days

    # ── Recency decay ────────────────────────────────────────────────────────
    recency_half_life_hours: float = 48.0  # hours until recency_score halves

    # ── Semantic store ───────────────────────────────────────────────────────
    chroma_collection_name: str = "memory_semantic"
    embedding_dim: int = 256  # matches LocalHashEmbeddingProvider default

    # ── Importance heuristics ────────────────────────────────────────────────
    high_importance_keywords: list[str] = field(
        default_factory=lambda: [
            "fraud",
            "locked",
            "lost",
            "stolen",
            "dispute",
            "complaint",
            "error",
            "urgent",
            "important",
            "remember",
            "always",
            "never",
            "prefer",
            "preference",
            "usually",
            "hate",
            "love",
        ]
    )
    high_importance_score: float = 0.85
    default_importance_score: float = 0.5


def get_memory_config() -> MemoryConfig:
    """Build MemoryConfig from environment variables with sane defaults."""
    return MemoryConfig(
        max_conversation_turns=int(os.environ.get("MEMORY_MAX_TURNS", 50)),
        max_long_term_memories=int(os.environ.get("MEMORY_MAX_LT", 200)),
        max_semantic_memories=int(os.environ.get("MEMORY_MAX_SEMANTIC", 500)),
        max_context_tokens=int(os.environ.get("MEMORY_MAX_CTX_TOKENS", 4000)),
        similarity_threshold=float(os.environ.get("MEMORY_SIM_THRESHOLD", 0.35)),
        top_k_semantic=int(os.environ.get("MEMORY_TOP_K_SEMANTIC", 5)),
        top_k_recency=int(os.environ.get("MEMORY_TOP_K_RECENCY", 10)),
        top_k_context=int(os.environ.get("MEMORY_TOP_K_CTX", 8)),
        summary_threshold_turns=int(os.environ.get("MEMORY_SUMMARY_THRESHOLD", 20)),
        summary_max_tokens=int(os.environ.get("MEMORY_SUMMARY_MAX_TOKENS", 600)),
        importance_weight=float(os.environ.get("MEMORY_IMPORTANCE_W", 0.4)),
        recency_weight=float(os.environ.get("MEMORY_RECENCY_W", 0.3)),
        relevance_weight=float(os.environ.get("MEMORY_RELEVANCE_W", 0.3)),
        session_ttl_days=int(os.environ.get("MEMORY_SESSION_TTL_DAYS", 90)),
        long_term_ttl_days=int(os.environ.get("MEMORY_LT_TTL_DAYS", 365)),
        conversation_ttl_days=int(os.environ.get("MEMORY_CONV_TTL_DAYS", 30)),
        recency_half_life_hours=float(os.environ.get("MEMORY_HALF_LIFE_HOURS", 48.0)),
        chroma_collection_name=os.environ.get(
            "MEMORY_CHROMA_COLLECTION", "memory_semantic"
        ),
    )
