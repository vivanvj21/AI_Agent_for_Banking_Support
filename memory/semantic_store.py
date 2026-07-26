"""
Memory Engine — semantic store (Chroma-backed).

Wraps the existing Chroma instance used by faq_search but in a
SEPARATE collection so memory vectors never pollute FAQ retrieval.
Falls back gracefully to a no-op store if Chroma is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from memory.config import MemoryConfig
from memory.models import MemoryEntry, MemorySearchResult, MemoryType

LOGGER = logging.getLogger(__name__)

# Lazy global Chroma client — only initialised once per process.
_chroma_client = None
_collection = None


def _get_collection(config: MemoryConfig):
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
    try:
        from pathlib import Path

        import chromadb

        persist_dir = str(
            Path(__file__).parent.parent / "knowledge_base" / "chroma_memory"
        )
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
        _collection = _chroma_client.get_or_create_collection(
            name=config.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        LOGGER.info(
            "memory_chroma_collection_ready",
            extra={"collection": config.chroma_collection_name},
        )
        return _collection
    except Exception as exc:
        LOGGER.warning("memory_chroma_unavailable", extra={"error": str(exc)})
        return None


def store_embedding(
    entry: MemoryEntry,
    embedding: list[float],
    config: MemoryConfig,
) -> bool:
    """Store a memory embedding in Chroma. Returns True on success."""
    col = _get_collection(config)
    if col is None:
        return False
    try:
        col.upsert(
            ids=[entry.memory_id],
            embeddings=[embedding],
            documents=[entry.content],
            metadatas=[
                {
                    "user_id": entry.user_id or "",
                    "session_id": entry.session_id or "",
                    "memory_type": entry.memory_type.value,
                    "importance": str(entry.importance),
                    "created_at": entry.created_at,
                }
            ],
        )
        return True
    except Exception as exc:
        LOGGER.warning("memory_chroma_store_failed", extra={"error": str(exc)})
        return False


def semantic_search(
    query_embedding: list[float],
    user_id: str | None,
    config: MemoryConfig,
    session_id: str | None = None,
    memory_types: list[MemoryType] | None = None,
    top_k: int | None = None,
) -> list[MemorySearchResult]:
    """
    Query Chroma for semantically similar memories.

    Filters by user_id (and optionally session_id / memory_type).
    Returns results above config.similarity_threshold.
    """
    col = _get_collection(config)
    if col is None:
        return []

    k = top_k or config.top_k_semantic
    where: dict[str, Any] = {}
    if user_id:
        where["user_id"] = user_id

    try:
        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(k, max(col.count(), 1)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        results = col.query(**query_kwargs)
    except Exception as exc:
        LOGGER.warning("memory_chroma_query_failed", extra={"error": str(exc)})
        return []

    hits: list[MemorySearchResult] = []
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for mid, dist, doc, meta in zip(ids, distances, documents, metadatas):
        # Chroma cosine distance: 0=identical, 2=opposite. Convert to similarity.
        similarity = 1.0 - (dist / 2.0)
        if similarity < config.similarity_threshold:
            continue

        # Filter by memory_type if requested
        if memory_types:
            mt_val = meta.get("memory_type", "")
            if not any(mt.value == mt_val for mt in memory_types):
                continue

        # Filter by session if requested
        if session_id and meta.get("session_id") != session_id:
            continue

        entry = MemoryEntry(
            memory_id=mid,
            user_id=meta.get("user_id") or None,
            session_id=meta.get("session_id") or None,
            memory_type=MemoryType(meta.get("memory_type", "long_term")),
            content=doc,
            importance=float(meta.get("importance", 0.5)),
            relevance_score=similarity,
        )
        hits.append(
            MemorySearchResult(entry=entry, score=similarity, match_type="semantic")
        )

    # Sort by similarity descending
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def delete_embedding(memory_id: str, config: MemoryConfig) -> None:
    col = _get_collection(config)
    if col is None:
        return
    try:
        col.delete(ids=[memory_id])
    except Exception as exc:
        LOGGER.warning("memory_chroma_delete_failed", extra={"error": str(exc)})


def delete_user_embeddings(user_id: str, config: MemoryConfig) -> int:
    """Delete all embeddings for a user from Chroma."""
    col = _get_collection(config)
    if col is None:
        return 0
    try:
        results = col.get(where={"user_id": user_id})
        ids = results.get("ids", [])
        if ids:
            col.delete(ids=ids)
        return len(ids)
    except Exception as exc:
        LOGGER.warning("memory_chroma_user_delete_failed", extra={"error": str(exc)})
        return 0
