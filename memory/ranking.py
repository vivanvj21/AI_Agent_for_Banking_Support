"""
Memory Engine — ranking module.

Computes importance, recency, and relevance scores for memories.
No external deps — pure Python / math.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from memory.config import MemoryConfig
from memory.models import MemoryEntry, MemoryType


def compute_recency_score(
    created_at: str,
    half_life_hours: float = 48.0,
) -> float:
    """
    Exponential decay based on age.
    score = 0.5 ^ (age_hours / half_life_hours)
    Returns a value in (0, 1].
    """
    try:
        created = datetime.fromisoformat(created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_hours = (now - created).total_seconds() / 3600.0
        score = math.pow(0.5, age_hours / half_life_hours)
        return max(0.001, min(1.0, score))
    except Exception:
        return 0.5


def compute_importance_score(
    content: str,
    config: MemoryConfig,
    memory_type: MemoryType | None = None,
) -> float:
    """
    Heuristic importance:
    - Long-term memories start at high_importance_score baseline
    - Content containing high-importance keywords → high_importance_score
    - Everything else → default_importance_score
    """
    if memory_type == MemoryType.LONG_TERM:
        return config.high_importance_score

    content_lower = content.lower()
    for kw in config.high_importance_keywords:
        if kw in content_lower:
            return config.high_importance_score

    # length heuristic: longer messages are usually more substantive
    word_count = len(content.split())
    length_bonus = min(0.15, word_count / 200.0)

    return min(1.0, config.default_importance_score + length_bonus)


def compute_relevance_score(
    query_embedding: list[float],
    memory_embedding: list[float],
) -> float:
    """Cosine similarity between query and memory embeddings."""
    if not query_embedding or not memory_embedding:
        return 0.0
    dot = sum(a * b for a, b in zip(query_embedding, memory_embedding))
    norm_a = math.sqrt(sum(a * a for a in query_embedding))
    norm_b = math.sqrt(sum(b * b for b in memory_embedding))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def rank_memories(
    memories: list[MemoryEntry],
    config: MemoryConfig,
    query_embedding: list[float] | None = None,
) -> list[MemoryEntry]:
    """
    Score and sort memories by composite score.
    Updates recency_score and (if query_embedding provided) relevance_score
    in place before ranking.
    """
    for entry in memories:
        entry.recency_score = compute_recency_score(
            entry.created_at, config.recency_half_life_hours
        )
        if query_embedding and entry.embedding:
            entry.relevance_score = compute_relevance_score(
                query_embedding, entry.embedding
            )

    memories.sort(
        key=lambda m: m.composite_score(
            config.importance_weight,
            config.recency_weight,
            config.relevance_weight,
        ),
        reverse=True,
    )
    return memories


def apply_recency_decay_batch(
    memories: list[MemoryEntry],
    half_life_hours: float,
) -> list[tuple[str, float]]:
    """Return (memory_id, new_recency_score) pairs for bulk update."""
    results = []
    for entry in memories:
        score = compute_recency_score(entry.created_at, half_life_hours)
        results.append((entry.memory_id, score))
    return results
