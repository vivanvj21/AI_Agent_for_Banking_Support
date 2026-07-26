"""
Memory Engine — abstract base class.

Defines the interface that any memory backend must implement.
Currently only SQLite+Chroma is implemented (via MemoryManager),
but this base makes it easy to swap backends (e.g. Redis, Postgres).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from memory.models import ContextPackage, MemoryEntry, MemorySearchResult


class BaseMemoryBackend(ABC):
    """Minimal interface that every memory backend must satisfy."""

    @abstractmethod
    def ensure_ready(self) -> None:
        """Initialise the backend (create tables, connect, etc.)."""

    @abstractmethod
    def record_turn(
        self,
        session_id: str,
        user_id: str | None,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Persist a conversation turn. Returns memory_id."""

    @abstractmethod
    def get_session_turns(
        self, session_id: str, limit: int | None = None
    ) -> list[MemoryEntry]:
        """Return recent conversation turns for a session."""

    @abstractmethod
    def remember_fact(
        self,
        user_id: str,
        content: str,
        importance: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Persist a long-term fact/preference. Returns memory_id."""

    @abstractmethod
    def get_long_term_facts(self, user_id: str, limit: int = 20) -> list[MemoryEntry]:
        """Return long-term memories for a user."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
    ) -> list[MemorySearchResult]:
        """Hybrid memory retrieval."""

    @abstractmethod
    def get_context(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
    ) -> ContextPackage:
        """Full retrieval + context assembly."""

    @abstractmethod
    def delete_memory(self, memory_id: str, hard: bool = False) -> None:
        """Delete (soft or hard) a memory entry."""

    @abstractmethod
    def expire_old_memories(self) -> dict:
        """Remove expired entries. Returns deletion stats."""
