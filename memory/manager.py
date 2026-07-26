"""
Memory Engine — MemoryManager (façade / orchestrator).

This is the single entry point that the graph nodes and agents use.
All lower-level modules (store, retriever, summarizer, ranking,
semantic_store) are called through here.

Usage from an agent::

    from memory.manager import MemoryManager

    mgr = MemoryManager()

    # After a user turn:
    mgr.record_turn(session_id, user_id, "user", user_message)
    mgr.record_turn(session_id, user_id, "assistant", reply)

    # Before calling the LLM:
    ctx = mgr.get_context(query=user_message, session_id=..., user_id=...)

    # Store a long-term fact extracted from the conversation:
    mgr.remember_fact(user_id, "User prefers SMS notifications.")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from memory import semantic_store as sem_store
from memory import store as mem_store
from memory.config import MemoryConfig, get_memory_config
from memory.context_builder import build_context
from memory.models import ContextPackage, MemoryEntry, MemorySearchResult, MemoryType
from memory.ranking import compute_importance_score
from memory.retriever import retrieve_all
from memory.summarizer import get_session_summary, should_summarize, summarize_session

LOGGER = logging.getLogger(__name__)

# Singleton-style: one manager per process (config is cheap to share)
_default_manager: MemoryManager | None = None


def get_memory_manager(config: MemoryConfig | None = None) -> MemoryManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = MemoryManager(config=config)
    return _default_manager


class MemoryManager:
    """Orchestrates all memory operations for the Banking Assistant."""

    def __init__(
        self,
        config: MemoryConfig | None = None,
        db_path: Path | None = None,
    ) -> None:
        self.config = config or get_memory_config()
        self.db_path = db_path
        self._schema_ready = False

    # ── Initialization ───────────────────────────────────────────────────────

    def ensure_ready(self) -> None:
        """Create memory tables if not already done. Safe to call multiple times."""
        if not self._schema_ready:
            mem_store.ensure_memory_schema(self.db_path)
            self._schema_ready = True

    # ── Conversation memory ───────────────────────────────────────────────────

    def record_turn(
        self,
        session_id: str,
        user_id: str | None,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Persist a conversation turn and embed it for semantic search."""
        self.ensure_ready()
        importance = compute_importance_score(content, self.config)
        memory_id = mem_store.store_conversation_turn(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            importance=importance,
            metadata=metadata,
            db_path=self.db_path,
        )
        # Async-style: attempt to embed (non-blocking failure)
        self._try_embed(
            memory_id, user_id, session_id, content, MemoryType.CONVERSATION
        )

        # Auto-summarize if session is long
        if should_summarize(session_id, self.config, self.db_path):
            try:
                summarize_session(
                    session_id=session_id,
                    user_id=user_id,
                    config=self.config,
                    db_path=self.db_path,
                    use_llm=True,
                )
            except Exception as exc:
                LOGGER.warning("auto_summarize_failed", extra={"error": str(exc)})

        return memory_id

    def get_session_turns(
        self, session_id: str, limit: int | None = None
    ) -> list[MemoryEntry]:
        """Return recent conversation turns for a session."""
        self.ensure_ready()
        lim = limit or self.config.max_conversation_turns
        return mem_store.load_conversation_turns(
            session_id, limit=lim, db_path=self.db_path
        )

    # ── Long-term memory ──────────────────────────────────────────────────────

    def remember_fact(
        self,
        user_id: str,
        content: str,
        importance: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a long-term fact/preference for a user."""
        self.ensure_ready()
        score = importance or compute_importance_score(
            content, self.config, MemoryType.LONG_TERM
        )
        memory_id = mem_store.store_long_term_memory(
            user_id=user_id,
            content=content,
            importance=score,
            metadata=metadata,
            ttl_days=self.config.long_term_ttl_days,
            db_path=self.db_path,
        )
        self._try_embed(memory_id, user_id, None, content, MemoryType.LONG_TERM)
        return memory_id

    def get_long_term_facts(self, user_id: str, limit: int = 20) -> list[MemoryEntry]:
        self.ensure_ready()
        return mem_store.load_long_term_memories(
            user_id, limit=limit, db_path=self.db_path
        )

    # ── User profile ──────────────────────────────────────────────────────────

    def update_user_profile(
        self,
        user_id: str,
        preferences: dict[str, Any] | None = None,
        facts: list[str] | None = None,
    ) -> None:
        self.ensure_ready()
        mem_store.upsert_user_profile(user_id, preferences, facts, self.db_path)

    def get_user_profile(self, user_id: str) -> dict:
        self.ensure_ready()
        return mem_store.load_user_profile(user_id, self.db_path)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
    ) -> list[MemorySearchResult]:
        """Hybrid retrieval: semantic + recency + importance + session."""
        self.ensure_ready()
        return retrieve_all(
            query=query,
            session_id=session_id,
            user_id=user_id,
            config=self.config,
            db_path=self.db_path,
        )

    # ── Context building ──────────────────────────────────────────────────────

    def get_context(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
    ) -> ContextPackage:
        """
        Full memory retrieval + context assembly pipeline.
        Call this before invoking an agent to get memory-enriched context.
        """
        results = self.retrieve(query, session_id, user_id)
        return build_context(
            query=query,
            session_id=session_id,
            user_id=user_id,
            memory_results=results,
            config=self.config,
            db_path=self.db_path,
        )

    # ── Summarization ─────────────────────────────────────────────────────────

    def get_session_summary(self, session_id: str) -> str | None:
        return get_session_summary(session_id, self.db_path)

    def force_summarize(
        self, session_id: str, user_id: str | None = None
    ) -> str | None:
        """Force a summarisation regardless of threshold."""
        return summarize_session(
            session_id=session_id,
            user_id=user_id,
            config=self.config,
            db_path=self.db_path,
            use_llm=True,
        )

    # ── Deletion / expiration ─────────────────────────────────────────────────

    def delete_memory(self, memory_id: str, hard: bool = False) -> None:
        """Soft or hard delete a memory entry."""
        self.ensure_ready()
        if hard:
            mem_store.delete_memory(memory_id, self.db_path)
            sem_store.delete_embedding(memory_id, self.config)
        else:
            mem_store.soft_delete_memory(memory_id, self.db_path)

    def expire_old_memories(self) -> dict:
        """Run expiration cleanup. Call at startup or on a schedule."""
        self.ensure_ready()
        return mem_store.cleanup_expired_memories(self.db_path)

    def cleanup_session_turns(self, session_id: str, keep: int = 20) -> int:
        """Trim old conversation turns for a session, keeping the N most recent."""
        self.ensure_ready()
        return mem_store.cleanup_old_conversation_turns(
            session_id, keep=keep, db_path=self.db_path
        )

    # ── Internal ─────────────────────────────────────────────────────────────

    def _try_embed(
        self,
        memory_id: str,
        user_id: str | None,
        session_id: str | None,
        content: str,
        memory_type: MemoryType,
    ) -> None:
        """Embed content and store in Chroma. Non-fatal on failure."""
        try:
            from tools.embeddings import get_default_provider

            provider = get_default_provider()
            embeddings = provider.embed([content])
            embedding = embeddings[0]

            from datetime import datetime, timezone

            from memory.models import MemoryEntry

            entry = MemoryEntry(
                memory_id=memory_id,
                user_id=user_id,
                session_id=session_id,
                memory_type=memory_type,
                content=content,
                importance=0.5,
                created_at=datetime.now(timezone.utc).isoformat(),
                last_accessed_at=datetime.now(timezone.utc).isoformat(),
            )
            sem_store.store_embedding(entry, embedding, self.config)
        except Exception as exc:
            LOGGER.debug("memory_embed_skipped", extra={"error": str(exc)})
