"""
RAG pipeline configuration.

All retrieval parameters that were previously hardcoded in tools/faq_search.py
live here so they can be tuned or overridden in tests without touching the
retrieval code.  Import ``RAGConfig`` and pass an instance to the functions
that accept it, or use ``DEFAULT_CONFIG`` for the production defaults.

Environment-variable overrides
-------------------------------
None of these values require a restart to change in tests — create a
``RAGConfig`` with different values and pass it explicitly.  For production
tuning, extend this module to read from env vars as needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RAGConfig:
    # ── Chunking ────────────────────────────────────────────────────────────
    chunk_size: int = 900
    """Maximum characters per chunk before splitting."""

    chunk_overlap: int = 120
    """Characters of overlap carried from one chunk to the next."""

    max_document_chars: int = 100_000
    """Hard limit on a single FAQ document; larger files are rejected."""

    # ── Retrieval ────────────────────────────────────────────────────────────
    default_k: int = 3
    """Default number of results returned by search_faq()."""

    max_k: int = 10
    """Upper bound on k accepted from callers."""

    # BM25 + dense fusion
    bm25_weight: float = 0.35
    """Weight given to BM25 (sparse) scores in Reciprocal Rank Fusion."""

    dense_weight: float = 0.65
    """Weight given to dense vector scores in Reciprocal Rank Fusion."""

    rrf_k: int = 60
    """Reciprocal Rank Fusion smoothing constant (standard value is 60)."""

    # Dense pre-fetch multiplier for MMR candidate pool
    mmr_fetch_multiplier: int = 4
    """How many extra candidates to fetch before MMR reranking."""

    mmr_lambda: float = 0.7
    """MMR diversity penalty. 1.0 = pure relevance, 0.0 = pure diversity."""

    # ── Query processing ─────────────────────────────────────────────────────
    max_query_chars: int = 1_000
    """Queries longer than this are silently truncated before embedding."""

    # ── Context window ───────────────────────────────────────────────────────
    max_context_chars: int = 1_200
    """Retrieved chunk text is truncated to this many characters before being
    returned to an LLM-facing agent."""

    # ── Supported file types ─────────────────────────────────────────────────
    supported_suffixes: frozenset[str] = field(
        default_factory=lambda: frozenset({".md", ".txt"})
    )
    """File extensions treated as FAQ source documents."""


# Production defaults — used by all callers that don't override.
DEFAULT_CONFIG = RAGConfig()
