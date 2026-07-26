"""
Memory Engine — context builder.

Assembles a ContextPackage from retrieved memories, long-term facts,
and session summaries.  Deduplicates content, compresses to fit within
the token budget, and returns a ready-to-use context object for agents.
"""

from __future__ import annotations

import logging
from pathlib import Path

from memory.config import MemoryConfig
from memory.models import ContextPackage, MemorySearchResult
from memory.summarizer import get_session_summary

LOGGER = logging.getLogger(__name__)

# Rough tokens-per-char approximation (4 chars ≈ 1 token for English)
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _deduplicate(texts: list[str], threshold: float = 0.85) -> list[str]:
    """
    Remove near-duplicate strings.
    Simple approach: skip if a candidate shares >threshold of its words
    with any already-accepted string.  O(n²) — fine for small lists.
    """
    accepted: list[str] = []
    accepted_word_sets: list[set[str]] = []
    for text in texts:
        words = set(text.lower().split())
        if not words:
            continue
        is_dup = False
        for existing_words in accepted_word_sets:
            overlap = len(words & existing_words) / len(words | existing_words)
            if overlap >= threshold:
                is_dup = True
                break
        if not is_dup:
            accepted.append(text)
            accepted_word_sets.append(words)
    return accepted


def _compress_to_budget(items: list[str], max_tokens: int) -> list[str]:
    """Greedily include items until we hit the token budget."""
    kept: list[str] = []
    total = 0
    for item in items:
        t = _estimate_tokens(item)
        if total + t > max_tokens:
            break
        kept.append(item)
        total += t
    return kept


def build_context(
    query: str,
    session_id: str,
    user_id: str | None,
    memory_results: list[MemorySearchResult],
    config: MemoryConfig,
    db_path: Path | None = None,
) -> ContextPackage:
    """
    Build a ContextPackage from retrieved memory results.

    Steps:
    1. Extract conversation history (recent turns)
    2. Extract long-term facts
    3. Pull session summary (if any)
    4. Deduplicate + compress to token budget
    5. Build system-context string
    """
    from memory.models import MemoryType

    # Separate by type
    conversation_entries = []
    long_term_entries = []

    for result in memory_results:
        entry = result.entry
        if entry.memory_type == MemoryType.CONVERSATION:
            conversation_entries.append(entry)
        elif entry.memory_type == MemoryType.LONG_TERM:
            long_term_entries.append(entry)

    # Build conversation history (oldest first for LLM consumption)
    conversation_entries.sort(key=lambda e: e.created_at)
    conversation_history = [
        {
            "role": (entry.role.value if entry.role else "user"),
            "content": entry.content,
        }
        for entry in conversation_entries
    ]

    # Extract long-term fact texts and deduplicate
    lt_texts = [e.content for e in long_term_entries]
    lt_texts = _deduplicate(lt_texts)

    # Load session summary
    summary = get_session_summary(session_id, db_path=db_path)

    # Build the system context block
    context_parts: list[str] = []

    if summary:
        context_parts.append(f"[Earlier conversation summary]\n{summary}")

    if lt_texts:
        facts_block = "\n".join(f"- {f}" for f in lt_texts)
        context_parts.append(f"[User long-term memory]\n{facts_block}")

    # Compress to token budget
    budget = config.max_context_tokens
    if conversation_history:
        # Reserve roughly half budget for conversation history
        conv_budget = budget // 2
        conv_texts = [f"{m['role']}: {m['content']}" for m in conversation_history]
        conv_texts = _compress_to_budget(conv_texts, conv_budget)
        # Rebuild after compression
        conversation_history = []
        for text in conv_texts:
            parts = text.split(": ", 1)
            if len(parts) == 2:
                conversation_history.append({"role": parts[0], "content": parts[1]})

    system_context_parts = _compress_to_budget(context_parts, budget // 2)
    system_context = "\n\n".join(system_context_parts)

    # Estimate total tokens
    all_text = system_context + " ".join(m["content"] for m in conversation_history)
    token_estimate = _estimate_tokens(all_text)

    sources = [r.entry.memory_id for r in memory_results[: config.top_k_context]]

    LOGGER.debug(
        "memory_context_built",
        extra={
            "session_id": session_id,
            "lt_facts": len(lt_texts),
            "conv_turns": len(conversation_history),
            "token_estimate": token_estimate,
        },
    )

    return ContextPackage(
        session_id=session_id,
        user_id=user_id,
        system_context=system_context,
        conversation_history=conversation_history,
        long_term_facts=lt_texts,
        summary=summary,
        token_estimate=token_estimate,
        sources=sources,
    )


def format_context_for_prompt(context: ContextPackage) -> str:
    """
    Convert a ContextPackage into a plain-text block suitable for
    injecting into a system prompt or prepending to conversation history.
    """
    parts = []

    if context.summary:
        parts.append(f"=== Conversation Summary ===\n{context.summary}")

    if context.long_term_facts:
        facts_str = "\n".join(f"• {f}" for f in context.long_term_facts)
        parts.append(f"=== User Facts & Preferences ===\n{facts_str}")

    if context.system_context and not parts:
        parts.append(context.system_context)

    return "\n\n".join(parts)
