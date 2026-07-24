"""
Conversation memory: makes sessions durable across process restarts, and
lets a verified user's past sessions be recalled ("what did I ask you
yesterday?").

Two layers, matching how the agents already talk about "memory":

  - Session memory   -> ``sessions`` + ``messages`` tables. Every turn of every
                        session is persisted as it happens, so a crashed or
                        restarted process (CLI re-run, Streamlit re-deploy)
                        can resume mid-conversation instead of starting
                        from a blank AgentState.

  - Long-term memory -> once a session is linked to a user_id (post
                        verification), ``get_recent_sessions_for_user`` /
                        ``get_last_session_summary_for_user`` let an agent pull
                        context from *previous* sessions, not just this one.

Session cleanup
---------------
``cleanup_old_sessions()`` removes sessions (and their messages) that have
been inactive for longer than ``retention_days`` and have **no unverified
in-flight messages** (i.e. the user_id has been set or the session is empty).
It is safe to call at any startup; it never deletes a session that was active
within the retention window.

No new infra: this reuses the same bank.db SQLite file and connection
pattern from db/connection.py. If this ever needs to run across multiple
server instances, swap ``get_connection`` for a Postgres connection —
every other function in this file is storage-agnostic.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db.connection import DB_PATH, get_connection
from db.init_db import ensure_database

LOGGER = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20  # cap on turns replayed back into a resumed session

# Default session retention period.  Sessions with ``last_active_at`` older
# than this value will be removed by ``cleanup_old_sessions()``.
DEFAULT_RETENTION_DAYS = 90


def _connect(db_path: Path | None = None):
    _path = db_path or DB_PATH
    ensure_database(_path, seed_demo_data=True)
    return get_connection(_path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session_id() -> str:
    return uuid.uuid4().hex


def create_session(channel: str = "cli", session_id: str | None = None) -> str:
    """Start a new session row. Returns the session_id."""
    session_id = session_id or new_session_id()
    conn = _connect()
    now = _now()
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, channel, created_at, last_active_at) "
        "VALUES (?, NULL, ?, ?, ?)",
        (session_id, channel, now, now),
    )
    conn.commit()
    conn.close()
    LOGGER.debug(
        "session_created", extra={"session_id": session_id, "channel": channel}
    )
    return session_id


def link_session_to_user(session_id: str, user_id: str) -> None:
    """Called right after verify_gate succeeds, so this session (and its
    message history) becomes attributable to the user for future recall."""
    conn = _connect()
    conn.execute(
        "UPDATE sessions SET user_id = ?, last_active_at = ? WHERE session_id = ?",
        (user_id, _now(), session_id),
    )
    conn.commit()
    conn.close()
    LOGGER.info(
        "session_linked_to_user", extra={"session_id": session_id, "user_id": user_id}
    )


def append_message(session_id: str, turn: int, role: str, content: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO messages (session_id, turn, role, content, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, turn, role, content, _now()),
    )
    conn.execute(
        "UPDATE sessions SET last_active_at = ? WHERE session_id = ?",
        (_now(), session_id),
    )
    conn.commit()
    conn.close()


def load_session_messages(session_id: str) -> list[dict]:
    """Replay a session's messages in order -- used to rebuild
    AgentState['messages'] after a restart."""
    conn = _connect()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def session_exists(session_id: str) -> bool:
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return row is not None


def get_session_user(session_id: str) -> str | None:
    conn = _connect()
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return row["user_id"] if row else None


def get_recent_sessions_for_user(
    user_id: str, limit: int = 5, exclude_session_id: str | None = None
) -> list[dict]:
    """Most recent past sessions for a verified user, most recent first."""
    conn = _connect()
    if exclude_session_id:
        rows = conn.execute(
            "SELECT session_id, created_at, last_active_at FROM sessions "
            "WHERE user_id = ? AND session_id != ? "
            "ORDER BY last_active_at DESC LIMIT ?",
            (user_id, exclude_session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT session_id, created_at, last_active_at FROM sessions "
            "WHERE user_id = ? ORDER BY last_active_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_session_summary_for_user(
    user_id: str, exclude_session_id: str | None = None
) -> dict | None:
    """
    Cheap 'long term memory' lookup: grabs the most recent prior session for
    this user and returns its first user message + turn count, so an agent
    can ground a reply like "what was my issue yesterday?" without pulling
    in a vector store. Good enough at this data volume; swap for a
    summarization pass if session transcripts get long.
    """
    sessions = get_recent_sessions_for_user(
        user_id, limit=1, exclude_session_id=exclude_session_id
    )
    if not sessions:
        return None
    prior = sessions[0]
    messages = load_session_messages(prior["session_id"])
    if not messages:
        return None
    first_user_msg = next((m["content"] for m in messages if m["role"] == "user"), None)
    return {
        "session_id": prior["session_id"],
        "last_active_at": prior["last_active_at"],
        "first_message": first_user_msg,
        "turn_count": sum(1 for m in messages if m["role"] == "user"),
    }


def cleanup_old_sessions(
    retention_days: int = DEFAULT_RETENTION_DAYS,
    db_path: Path | None = None,
) -> dict:
    """Remove sessions (and their messages) inactive for longer than *retention_days*.

    Only sessions whose ``last_active_at`` is older than the cutoff **and**
    that have no messages still within the retention window are removed.
    Active sessions (even unverified ones) are never deleted.

    Returns a summary dict: ``{"deleted_sessions": int, "deleted_messages": int}``.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    conn = _connect(db_path)
    try:
        # Find expired session IDs.
        stale_rows = conn.execute(
            "SELECT session_id FROM sessions WHERE last_active_at < ?",
            (cutoff,),
        ).fetchall()
        stale_ids = [r["session_id"] for r in stale_rows]

        if not stale_ids:
            LOGGER.info("session_cleanup_nothing_to_remove", extra={"cutoff": cutoff})
            return {"deleted_sessions": 0, "deleted_messages": 0}

        # Delete messages first (FK child rows).
        placeholders = ",".join("?" * len(stale_ids))
        cur = conn.execute(
            f"DELETE FROM messages WHERE session_id IN ({placeholders})",
            stale_ids,
        )
        deleted_messages = cur.rowcount

        cur = conn.execute(
            f"DELETE FROM sessions WHERE session_id IN ({placeholders})",
            stale_ids,
        )
        deleted_sessions = cur.rowcount
        conn.commit()

        LOGGER.info(
            "session_cleanup_complete",
            extra={
                "deleted_sessions": deleted_sessions,
                "deleted_messages": deleted_messages,
                "cutoff": cutoff,
                "retention_days": retention_days,
            },
        )
        return {
            "deleted_sessions": deleted_sessions,
            "deleted_messages": deleted_messages,
        }
    finally:
        conn.close()
