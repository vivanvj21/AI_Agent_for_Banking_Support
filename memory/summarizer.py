"""
Memory Engine — summarizer.

When a session exceeds config.summary_threshold_turns, condenses
older turns into a compact summary using the LLM (Claude).

Falls back to an extractive summary (first sentence per turn) if the
LLM call fails, so memory always produces *something*.
"""

from __future__ import annotations

import logging
from pathlib import Path

from memory import store as mem_store
from memory.config import MemoryConfig
from memory.models import MemoryEntry, MemoryType

LOGGER = logging.getLogger(__name__)


def _extractive_summary(turns: list[MemoryEntry], max_chars: int = 800) -> str:
    """
    Cheap extractive fallback: concatenate the first sentence of each turn,
    truncated to max_chars. Used when the LLM is unavailable.
    """
    lines = []
    for entry in turns:
        role = entry.role.value if entry.role else "unknown"
        first_sentence = entry.content.split(".")[0].strip()
        if first_sentence:
            lines.append(f"{role}: {first_sentence}.")
    summary = " ".join(lines)
    return summary[:max_chars] if len(summary) > max_chars else summary


def _llm_summary(turns: list[MemoryEntry], max_tokens: int = 600) -> str | None:
    """
    Use Claude to generate a compact summary of a list of conversation turns.
    Returns None on failure so callers can fall back.
    """
    try:
        from anthropic import Anthropic

        from config import require_llm_config

        config = require_llm_config()
        client = Anthropic(api_key=config.api_key)

        conversation_text = "\n".join(
            f"{(entry.role.value if entry.role else 'unknown').upper()}: {entry.content}"
            for entry in turns
        )

        response = client.messages.create(
            model="claude-haiku-4-5",  # cheap model for summarisation
            max_tokens=max_tokens,
            system=(
                "You are a concise conversation summariser for a banking assistant. "
                "Summarise the key facts, user requests, and outcomes from the conversation below "
                "in 3-5 bullet points. Focus on: account actions, user preferences, issues raised, "
                "and any unresolved questions. Be very brief."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Summarise this conversation:\n\n{conversation_text}",
                }
            ],
        )
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks).strip() or None
    except Exception as exc:
        LOGGER.warning("memory_llm_summary_failed", extra={"error": str(exc)})
        return None


def should_summarize(
    session_id: str,
    config: MemoryConfig,
    db_path: Path | None = None,
) -> bool:
    """Return True if the session has enough turns to warrant summarisation."""
    from db.connection import DB_PATH, get_connection

    conn = get_connection(db_path or DB_PATH)
    try:
        row = conn.execute(
            """SELECT COUNT(*) as n FROM memory_entries
               WHERE session_id = ? AND memory_type = ? AND is_deleted = 0""",
            (session_id, MemoryType.CONVERSATION.value),
        ).fetchone()
        count = row["n"] if row else 0
        return count >= config.summary_threshold_turns
    finally:
        conn.close()


def summarize_session(
    session_id: str,
    user_id: str | None,
    config: MemoryConfig,
    db_path: Path | None = None,
    use_llm: bool = True,
) -> str | None:
    """
    Summarise the oldest turns of a session, persist the summary,
    and soft-delete the summarised turns to save tokens.

    Returns the summary text (or None if nothing to summarise).
    """
    turns = mem_store.load_conversation_turns(
        session_id,
        limit=config.max_conversation_turns,
        db_path=db_path,
    )
    if len(turns) < config.summary_threshold_turns:
        return None

    # Summarise all-but-last 10 turns (keep recent turns verbatim)
    keep_verbatim = 10
    to_summarize = turns[:-keep_verbatim] if len(turns) > keep_verbatim else turns

    if not to_summarize:
        return None

    # Generate summary
    summary_text = None
    if use_llm:
        summary_text = _llm_summary(to_summarize, max_tokens=config.summary_max_tokens)
    if not summary_text:
        summary_text = _extractive_summary(to_summarize)

    if not summary_text:
        return None

    # Determine turn range
    turn_start = 0
    turn_end = len(to_summarize) - 1

    # Persist summary
    mem_store.store_summary(
        session_id=session_id,
        content=summary_text,
        turn_start=turn_start,
        turn_end=turn_end,
        user_id=user_id,
        db_path=db_path,
    )

    # Soft-delete the summarised turns
    from db.connection import DB_PATH, get_connection

    summarized_ids = [t.memory_id for t in to_summarize]
    if summarized_ids:
        placeholders = ",".join("?" * len(summarized_ids))
        conn = get_connection(db_path or DB_PATH)
        try:
            conn.execute(
                f"UPDATE memory_entries SET is_deleted=1 WHERE memory_id IN ({placeholders})",
                summarized_ids,
            )
            conn.commit()
        finally:
            conn.close()

    LOGGER.info(
        "memory_session_summarized",
        extra={
            "session_id": session_id,
            "turns_summarized": len(to_summarize),
            "summary_length": len(summary_text),
        },
    )
    return summary_text


def get_session_summary(
    session_id: str,
    db_path: Path | None = None,
) -> str | None:
    """Return the most recent summary for a session (if any)."""
    summaries = mem_store.load_summaries(session_id, db_path=db_path)
    if not summaries:
        return None
    # Return the latest summary
    return summaries[-1]["content"]
