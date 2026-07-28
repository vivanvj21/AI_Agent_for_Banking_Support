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
    """Build MemoryConfig from central settings."""
    from config import settings
    mem = settings.memory
    return MemoryConfig(
        max_conversation_turns=mem.max_conversation_turns,
        max_long_term_memories=mem.max_long_term_memories,
        max_semantic_memories=mem.max_semantic_memories,
        max_context_tokens=mem.max_context_tokens,
        similarity_threshold=mem.similarity_threshold,
        top_k_semantic=mem.top_k_semantic,
        top_k_recency=mem.top_k_recency,
        top_k_context=mem.top_k_context,
        summary_threshold_turns=mem.summary_threshold_turns,
        summary_max_tokens=mem.summary_max_tokens,
        importance_weight=mem.importance_weight,
        recency_weight=mem.recency_weight,
        relevance_weight=mem.relevance_weight,
        session_ttl_days=mem.session_ttl_days,
        long_term_ttl_days=mem.long_term_ttl_days,
        conversation_ttl_days=mem.conversation_ttl_days,
        recency_half_life_hours=mem.recency_half_life_hours,
        chroma_collection_name=mem.chroma_collection_name,
    )
