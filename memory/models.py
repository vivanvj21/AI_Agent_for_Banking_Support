"""
Memory Engine — data models.

All in-memory objects use dataclasses so there's no Pydantic dependency.
Serialization to/from SQLite rows is handled per-module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    CONVERSATION = "conversation"  # a single message turn
    SESSION = "session"  # session-level context blob
    LONG_TERM = "long_term"  # persistent user facts/preferences
    SEMANTIC = "semantic"  # embedding-indexed chunk


class MemoryRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class MemoryEntry:
    """A single unit of memory — one row in the memory_entries table."""

    memory_id: str  # uuid4 hex
    user_id: str | None  # None until session is verified
    session_id: str | None  # None for global long-term facts
    memory_type: MemoryType
    content: str  # raw text
    role: MemoryRole | None = None  # set for conversation turns
    importance: float = 0.5  # 0-1, computed by ranking
    recency_score: float = 1.0  # decays over time
    relevance_score: float = 0.0  # set at retrieval time via similarity
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None  # stored separately in chroma
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_accessed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: str | None = None  # ISO timestamp; None = never expires
    is_deleted: bool = False  # soft delete

    def composite_score(
        self,
        importance_w: float = 0.4,
        recency_w: float = 0.3,
        relevance_w: float = 0.3,
    ) -> float:
        """Weighted composite score used for ranking retrieved memories."""
        return (
            importance_w * self.importance
            + recency_w * self.recency_score
            + relevance_w * self.relevance_score
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "role": self.role.value if self.role else None,
            "importance": self.importance,
            "recency_score": self.recency_score,
            "relevance_score": self.relevance_score,
            "metadata": json.dumps(self.metadata),
            "embedding": json.dumps(self.embedding) if self.embedding else None,
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "expires_at": self.expires_at,
            "is_deleted": int(self.is_deleted),
        }

    @classmethod
    def from_row(cls, row: dict) -> MemoryEntry:
        metadata = row.get("metadata") or "{}"
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        embedding_raw = row.get("embedding")
        embedding = json.loads(embedding_raw) if embedding_raw else None
        return cls(
            memory_id=row["memory_id"],
            user_id=row.get("user_id"),
            session_id=row.get("session_id"),
            memory_type=MemoryType(row["memory_type"]),
            content=row["content"],
            role=MemoryRole(row["role"]) if row.get("role") else None,
            importance=float(row.get("importance", 0.5)),
            recency_score=float(row.get("recency_score", 1.0)),
            relevance_score=float(row.get("relevance_score", 0.0)),
            metadata=metadata,
            embedding=embedding,
            created_at=row.get("created_at", ""),
            last_accessed_at=row.get("last_accessed_at", ""),
            expires_at=row.get("expires_at"),
            is_deleted=bool(row.get("is_deleted", 0)),
        )


@dataclass
class SessionContext:
    """Runtime context object passed between graph nodes."""

    session_id: str
    user_id: str | None = None
    verified: bool = False
    channel: str = "cli"
    active_memories: list[MemoryEntry] = field(default_factory=list)
    summary: str | None = None  # compressed summary of older turns
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySearchResult:
    """Result from a semantic or hybrid memory search."""

    entry: MemoryEntry
    score: float
    match_type: str = "semantic"  # "semantic" | "recency" | "importance" | "session"


@dataclass
class ContextPackage:
    """
    The assembled prompt context handed to an agent.
    Holds the merged, deduplicated, compressed memory for a turn.
    """

    session_id: str
    user_id: str | None
    system_context: str  # full system-level context string
    conversation_history: list[dict]  # [{role, content}] ready for LLM
    long_term_facts: list[str]  # bullet list of recalled facts
    summary: str | None = None  # summary of earlier turns
    token_estimate: int = 0
    sources: list[str] = field(default_factory=list)  # memory_ids used
