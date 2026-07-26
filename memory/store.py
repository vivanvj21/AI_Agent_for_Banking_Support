"""
Memory Engine — SQLite persistence layer.

Reuses db/connection.py (bank.db) — no new database.
The memory_entries table is added by memory/schema.sql via
ensure_memory_schema() which is called once at import time by MemoryManager.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from db.connection import DB_PATH, get_connection
from memory.models import MemoryEntry, MemoryType

LOGGER = logging.getLogger(__name__)

_MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entries (
    memory_id        TEXT PRIMARY KEY,
    user_id          TEXT,
    session_id       TEXT,
    memory_type      TEXT NOT NULL,
    content          TEXT NOT NULL,
    role             TEXT,
    importance       REAL NOT NULL DEFAULT 0.5,
    recency_score    REAL NOT NULL DEFAULT 1.0,
    relevance_score  REAL NOT NULL DEFAULT 0.0,
    metadata         TEXT NOT NULL DEFAULT '{}',
    created_at       TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    expires_at       TEXT,
    is_deleted       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memory_user_id    ON memory_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_session_id ON memory_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_type       ON memory_entries(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_created    ON memory_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_expires    ON memory_entries(expires_at);

CREATE TABLE IF NOT EXISTS memory_summaries (
    summary_id   TEXT PRIMARY KEY,
    user_id      TEXT,
    session_id   TEXT NOT NULL,
    content      TEXT NOT NULL,
    turn_start   INTEGER NOT NULL,
    turn_end     INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summary_session ON memory_summaries(session_id);
CREATE INDEX IF NOT EXISTS idx_summary_user    ON memory_summaries(user_id);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id      TEXT PRIMARY KEY,
    preferences  TEXT NOT NULL DEFAULT '{}',
    facts        TEXT NOT NULL DEFAULT '[]',
    updated_at   TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def ensure_memory_schema(db_path: Path | None = None) -> None:
    """Create memory tables if they don't exist.  Idempotent."""
    conn = get_connection(db_path or DB_PATH)
    try:
        conn.executescript(_MEMORY_SCHEMA)
        conn.commit()
        LOGGER.debug("memory_schema_ready")
    finally:
        conn.close()


# ─── Conversation / Session memory ──────────────────────────────────────────


def store_conversation_turn(
    session_id: str,
    user_id: str | None,
    role: str,
    content: str,
    importance: float = 0.5,
    metadata: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> str:
    """Persist one conversation turn.  Returns memory_id."""
    memory_id = _new_id()
    entry = MemoryEntry(
        memory_id=memory_id,
        user_id=user_id,
        session_id=session_id,
        memory_type=MemoryType.CONVERSATION,
        content=content,
        role=None,  # stored as separate field
        importance=importance,
        metadata=metadata or {},
        created_at=_now(),
        last_accessed_at=_now(),
    )
    row = entry.to_dict()
    row["role"] = role  # override — role is a plain string here
    conn = get_connection(db_path or DB_PATH)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO memory_entries
               (memory_id, user_id, session_id, memory_type, content, role,
                importance, recency_score, relevance_score, metadata,
                created_at, last_accessed_at, expires_at, is_deleted)
               VALUES (:memory_id, :user_id, :session_id, :memory_type, :content, :role,
                       :importance, :recency_score, :relevance_score, :metadata,
                       :created_at, :last_accessed_at, :expires_at, :is_deleted)""",
            row,
        )
        conn.commit()
    finally:
        conn.close()
    return memory_id


def load_conversation_turns(
    session_id: str,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[MemoryEntry]:
    """Return conversation turns for a session, oldest first."""
    conn = get_connection(db_path or DB_PATH)
    try:
        rows = conn.execute(
            """SELECT * FROM memory_entries
               WHERE session_id = ? AND memory_type = ? AND is_deleted = 0
               ORDER BY created_at ASC LIMIT ?""",
            (session_id, MemoryType.CONVERSATION.value, limit),
        ).fetchall()
        return [MemoryEntry.from_row(dict(r)) for r in rows]
    finally:
        conn.close()


# ─── Long-term memory ────────────────────────────────────────────────────────


def store_long_term_memory(
    user_id: str,
    content: str,
    importance: float = 0.7,
    metadata: dict[str, Any] | None = None,
    ttl_days: int | None = None,
    db_path: Path | None = None,
) -> str:
    """Persist a long-term fact / preference for a user.  Returns memory_id."""
    memory_id = _new_id()
    expires_at = None
    if ttl_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
    entry = MemoryEntry(
        memory_id=memory_id,
        user_id=user_id,
        session_id=None,
        memory_type=MemoryType.LONG_TERM,
        content=content,
        importance=importance,
        metadata=metadata or {},
        expires_at=expires_at,
        created_at=_now(),
        last_accessed_at=_now(),
    )
    row = entry.to_dict()
    conn = get_connection(db_path or DB_PATH)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO memory_entries
               (memory_id, user_id, session_id, memory_type, content, role,
                importance, recency_score, relevance_score, metadata,
                created_at, last_accessed_at, expires_at, is_deleted)
               VALUES (:memory_id, :user_id, :session_id, :memory_type, :content, :role,
                       :importance, :recency_score, :relevance_score, :metadata,
                       :created_at, :last_accessed_at, :expires_at, :is_deleted)""",
            row,
        )
        conn.commit()
        LOGGER.info(
            "long_term_memory_stored",
            extra={"user_id": user_id, "memory_id": memory_id},
        )
    finally:
        conn.close()
    return memory_id


def load_long_term_memories(
    user_id: str,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[MemoryEntry]:
    """Return non-expired long-term memories for a user, by importance desc."""
    now = _now()
    conn = get_connection(db_path or DB_PATH)
    try:
        rows = conn.execute(
            """SELECT * FROM memory_entries
               WHERE user_id = ? AND memory_type = ? AND is_deleted = 0
               AND (expires_at IS NULL OR expires_at > ?)
               ORDER BY importance DESC, created_at DESC LIMIT ?""",
            (user_id, MemoryType.LONG_TERM.value, now, limit),
        ).fetchall()
        return [MemoryEntry.from_row(dict(r)) for r in rows]
    finally:
        conn.close()


# ─── User profile ────────────────────────────────────────────────────────────


def upsert_user_profile(
    user_id: str,
    preferences: dict[str, Any] | None = None,
    facts: list[str] | None = None,
    db_path: Path | None = None,
) -> None:
    """Create or update the user_profiles row."""
    conn = get_connection(db_path or DB_PATH)
    try:
        row = conn.execute(
            "SELECT preferences, facts FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            existing_prefs = json.loads(row["preferences"])
            existing_facts = json.loads(row["facts"])
            if preferences:
                existing_prefs.update(preferences)
            if facts:
                # deduplicate
                existing_facts = list(dict.fromkeys(existing_facts + facts))
            conn.execute(
                "UPDATE user_profiles SET preferences=?, facts=?, updated_at=? WHERE user_id=?",
                (
                    json.dumps(existing_prefs),
                    json.dumps(existing_facts),
                    _now(),
                    user_id,
                ),
            )
        else:
            conn.execute(
                "INSERT INTO user_profiles (user_id, preferences, facts, updated_at) VALUES (?, ?, ?, ?)",
                (
                    user_id,
                    json.dumps(preferences or {}),
                    json.dumps(facts or []),
                    _now(),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def load_user_profile(user_id: str, db_path: Path | None = None) -> dict:
    """Return {preferences: {}, facts: []} for a user."""
    conn = get_connection(db_path or DB_PATH)
    try:
        row = conn.execute(
            "SELECT preferences, facts FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return {"preferences": {}, "facts": []}
        return {
            "preferences": json.loads(row["preferences"]),
            "facts": json.loads(row["facts"]),
        }
    finally:
        conn.close()


# ─── Memory summaries ────────────────────────────────────────────────────────


def store_summary(
    session_id: str,
    content: str,
    turn_start: int,
    turn_end: int,
    user_id: str | None = None,
    db_path: Path | None = None,
) -> str:
    summary_id = _new_id()
    conn = get_connection(db_path or DB_PATH)
    try:
        conn.execute(
            """INSERT INTO memory_summaries
               (summary_id, user_id, session_id, content, turn_start, turn_end, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (summary_id, user_id, session_id, content, turn_start, turn_end, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return summary_id


def load_summaries(
    session_id: str,
    db_path: Path | None = None,
) -> list[dict]:
    conn = get_connection(db_path or DB_PATH)
    try:
        rows = conn.execute(
            "SELECT * FROM memory_summaries WHERE session_id = ? ORDER BY turn_start ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Generic retrieval ───────────────────────────────────────────────────────


def load_by_ids(
    memory_ids: list[str],
    db_path: Path | None = None,
) -> list[MemoryEntry]:
    if not memory_ids:
        return []
    placeholders = ",".join("?" * len(memory_ids))
    conn = get_connection(db_path or DB_PATH)
    try:
        rows = conn.execute(
            f"SELECT * FROM memory_entries WHERE memory_id IN ({placeholders}) AND is_deleted = 0",
            memory_ids,
        ).fetchall()
        return [MemoryEntry.from_row(dict(r)) for r in rows]
    finally:
        conn.close()


def update_recency_scores(
    memory_ids: list[str],
    scores: list[float],
    db_path: Path | None = None,
) -> None:
    if not memory_ids:
        return
    now = _now()
    conn = get_connection(db_path or DB_PATH)
    try:
        for mid, score in zip(memory_ids, scores):
            conn.execute(
                "UPDATE memory_entries SET recency_score=?, last_accessed_at=? WHERE memory_id=?",
                (score, now, mid),
            )
        conn.commit()
    finally:
        conn.close()


# ─── Deletion / expiration ───────────────────────────────────────────────────


def soft_delete_memory(memory_id: str, db_path: Path | None = None) -> None:
    conn = get_connection(db_path or DB_PATH)
    try:
        conn.execute(
            "UPDATE memory_entries SET is_deleted = 1 WHERE memory_id = ?",
            (memory_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_memory(memory_id: str, db_path: Path | None = None) -> None:
    """Hard delete a single memory entry."""
    conn = get_connection(db_path or DB_PATH)
    try:
        conn.execute("DELETE FROM memory_entries WHERE memory_id = ?", (memory_id,))
        conn.commit()
    finally:
        conn.close()


def cleanup_expired_memories(db_path: Path | None = None) -> dict:
    """Hard-delete rows whose expires_at has passed."""
    now = _now()
    conn = get_connection(db_path or DB_PATH)
    try:
        cur = conn.execute(
            "DELETE FROM memory_entries WHERE expires_at IS NOT NULL AND expires_at < ? AND is_deleted = 0",
            (now,),
        )
        deleted = cur.rowcount
        conn.commit()
        LOGGER.info("memory_expired_cleanup", extra={"deleted": deleted})
        return {"deleted_entries": deleted}
    finally:
        conn.close()


def cleanup_old_conversation_turns(
    session_id: str,
    keep: int = 20,
    db_path: Path | None = None,
) -> int:
    """Keep only the N most recent conversation turns for a session."""
    conn = get_connection(db_path or DB_PATH)
    try:
        rows = conn.execute(
            """SELECT memory_id FROM memory_entries
               WHERE session_id = ? AND memory_type = ? AND is_deleted = 0
               ORDER BY created_at DESC""",
            (session_id, MemoryType.CONVERSATION.value),
        ).fetchall()
        ids_to_keep = {r["memory_id"] for r in rows[:keep]}
        all_ids = [r["memory_id"] for r in rows]
        to_delete = [mid for mid in all_ids if mid not in ids_to_keep]
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            conn.execute(
                f"UPDATE memory_entries SET is_deleted=1 WHERE memory_id IN ({placeholders})",
                to_delete,
            )
            conn.commit()
        return len(to_delete)
    finally:
        conn.close()
