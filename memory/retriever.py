"""
Memory Engine — retriever.

Implements multi-strategy retrieval:
  1. Session-scoped (recent conversation turns)
  2. Recency-sorted (most recent across sessions for a user)
  3. Importance-sorted (highest importance facts)
  4. Semantic similarity (via Chroma)

Results are merged, deduplicated, and returned as MemorySearchResult objects.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from memory import semantic_store as sem_store
from memory import store as mem_store
from memory.config import MemoryConfig
from memory.models import MemoryEntry, MemorySearchResult, MemoryType
from memory.ranking import compute_recency_score, rank_memories

LOGGER = logging.getLogger(__name__)


def retrieve_session_memories(
    session_id: str,
    config: MemoryConfig,
    limit: int | None = None,
    db_path: Path | None = None,
) -> list[MemorySearchResult]:
    """Return recent conversation turns for a session."""
    lim = limit or config.top_k_recency
    entries = mem_store.load_conversation_turns(session_id, limit=lim, db_path=db_path)
    results = []
    for entry in entries:
        entry.recency_score = compute_recency_score(
            entry.created_at, config.recency_half_life_hours
        )
        results.append(
            MemorySearchResult(
                entry=entry, score=entry.recency_score, match_type="session"
            )
        )
    return results


def retrieve_by_recency(
    user_id: str,
    config: MemoryConfig,
    memory_types: list[MemoryType] | None = None,
    db_path: Path | None = None,
) -> list[MemorySearchResult]:
    """Return most recent memories across all sessions for a user."""
    from db.connection import DB_PATH, get_connection

    types = memory_types or [MemoryType.LONG_TERM, MemoryType.CONVERSATION]
    placeholders = ",".join("?" * len(types))
    type_values = [t.value for t in types]
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection(db_path or DB_PATH)
    try:
        rows = conn.execute(
            f"""SELECT * FROM memory_entries
                WHERE user_id = ? AND memory_type IN ({placeholders})
                AND is_deleted = 0
                AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC LIMIT ?""",
            [user_id] + type_values + [now, config.top_k_recency],
        ).fetchall()
        entries = [MemoryEntry.from_row(dict(r)) for r in rows]
    finally:
        conn.close()

    results = []
    for entry in entries:
        entry.recency_score = compute_recency_score(
            entry.created_at, config.recency_half_life_hours
        )
        results.append(
            MemorySearchResult(
                entry=entry, score=entry.recency_score, match_type="recency"
            )
        )
    return results


def retrieve_by_importance(
    user_id: str,
    config: MemoryConfig,
    db_path: Path | None = None,
) -> list[MemorySearchResult]:
    """Return highest-importance long-term memories for a user."""
    entries = mem_store.load_long_term_memories(
        user_id, limit=config.top_k_recency, db_path=db_path
    )
    results = []
    for entry in entries:
        results.append(
            MemorySearchResult(
                entry=entry, score=entry.importance, match_type="importance"
            )
        )
    return results


def retrieve_semantic(
    query: str,
    user_id: str | None,
    config: MemoryConfig,
    session_id: str | None = None,
    memory_types: list[MemoryType] | None = None,
) -> list[MemorySearchResult]:
    """
    Embed the query and do a cosine similarity search in Chroma.
    Falls back to empty list if embeddings are unavailable.
    """
    try:
        from tools.embeddings import get_default_provider

        provider = get_default_provider()
        embeddings = provider.embed([query])
        query_embedding = embeddings[0]
    except Exception as exc:
        LOGGER.warning("memory_embed_query_failed", extra={"error": str(exc)})
        return []

    return sem_store.semantic_search(
        query_embedding=query_embedding,
        user_id=user_id,
        config=config,
        session_id=session_id,
        memory_types=memory_types,
    )


def retrieve_all(
    query: str,
    session_id: str,
    user_id: str | None,
    config: MemoryConfig,
    db_path: Path | None = None,
) -> list[MemorySearchResult]:
    """
    Hybrid retrieval: merges semantic + recency + importance + session.
    Deduplicates by memory_id. Returns top_k_context results ranked by
    composite score.
    """
    seen_ids: set[str] = set()
    merged: list[MemorySearchResult] = []

    def _add(results: list[MemorySearchResult]) -> None:
        for r in results:
            if r.entry.memory_id not in seen_ids:
                seen_ids.add(r.entry.memory_id)
                merged.append(r)

    # 1. Session memory (most recent turns of THIS session)
    _add(retrieve_session_memories(session_id, config, db_path=db_path))

    if user_id:
        # 2. Semantic search across user's stored memories
        _add(retrieve_semantic(query, user_id, config, session_id=session_id))

        # 3. High-importance long-term facts
        _add(retrieve_by_importance(user_id, config, db_path=db_path))

        # 4. Recent memories (last N)
        _add(retrieve_by_recency(user_id, config, db_path=db_path))

    # Re-rank everything by composite score, then truncate
    entries = [r.entry for r in merged]
    try:
        from tools.embeddings import get_default_provider

        provider = get_default_provider()
        query_emb = provider.embed([query])[0]
    except Exception:
        query_emb = None

    ranked = rank_memories(entries, config, query_embedding=query_emb)
    top = ranked[: config.top_k_context]

    # Rebuild MemorySearchResult objects in ranked order
    score_map = {r.entry.memory_id: r for r in merged}
    final: list[MemorySearchResult] = []
    for entry in top:
        orig = score_map.get(entry.memory_id)
        if orig:
            orig.entry = entry  # update scores in-place
            final.append(orig)
        else:
            final.append(
                MemorySearchResult(
                    entry=entry,
                    score=entry.composite_score(
                        config.importance_weight,
                        config.recency_weight,
                        config.relevance_weight,
                    ),
                )
            )
    return final
