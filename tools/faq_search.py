"""
FAQ / policy document search tool — enterprise-grade RAG pipeline.

Retrieval stages
----------------
1. **Markdown-aware chunking** (header + paragraph hierarchy preserved).
2. **Incremental indexing** — content-addressed chunk IDs; stale chunks pruned
   automatically on each ``build_index`` call.
3. **Hybrid retrieval** — BM25 (sparse) + dense vector search fused via
   Reciprocal Rank Fusion (RRF), then reranked with MMR for diversity.
4. **Query normalization** — whitespace collapse, length cap, stop-word-light
   normalisation before embedding and BM25 tokenisation.
5. **Rich metadata** — section name, heading hierarchy, document version
   (SHA-256 of full doc), chunk number, tags derived from headings.
6. **Sanitisation** — prompt-injection markers stripped from every retrieved
   chunk before it reaches an LLM-facing agent.

Backwards compatibility
-----------------------
All public names and function signatures from the original implementation are
preserved exactly so that:
  • ``agents/search_agent.py`` continues to call ``search_faq()`` unchanged.
  • ``config.py`` continues to call ``build_index()`` unchanged.
  • ``api/routes.py`` continues to call ``search_faq()`` and ``build_index()``
    unchanged.
  • All existing ``test_faq_search.py`` fixtures (monkeypatching ``FAQ_DIR``,
    ``CHROMA_PATH``, ``_collection``, ``_provider``, ``get_default_provider``,
    ``MAX_DOCUMENT_CHARS``) still work without modification.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from tools.embeddings import get_default_provider
from tools.rag_config import DEFAULT_CONFIG, RAGConfig

LOGGER = logging.getLogger(__name__)

# ── Module-level constants (preserved for existing monkeypatch fixtures) ──────
FAQ_DIR = Path(__file__).parent.parent / "knowledge_base" / "faq_docs"
CHROMA_PATH = Path(__file__).parent.parent / "knowledge_base" / "chroma_store"
COLLECTION_NAME = "faq_docs"
SUPPORTED_SUFFIXES = {".md", ".txt"}

# These are kept as bare module-level names so existing tests can monkeypatch them.
MAX_DOCUMENT_CHARS = DEFAULT_CONFIG.max_document_chars
MAX_QUERY_CHARS = DEFAULT_CONFIG.max_query_chars
MAX_CONTEXT_CHARS = DEFAULT_CONFIG.max_context_chars
MAX_K = DEFAULT_CONFIG.max_k
DEFAULT_CHUNK_SIZE = DEFAULT_CONFIG.chunk_size
DEFAULT_CHUNK_OVERLAP = DEFAULT_CONFIG.chunk_overlap
MMR_FETCH_MULTIPLIER = DEFAULT_CONFIG.mmr_fetch_multiplier
MMR_LAMBDA = DEFAULT_CONFIG.mmr_lambda

_collection = None
_provider = None


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DocumentChunk:
    """A safely indexed text chunk with stable, rich metadata."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


# ── Text utilities ─────────────────────────────────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    """Normalize whitespace for stable hashing/indexing without losing content."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_query(query: str, max_chars: int = MAX_QUERY_CHARS) -> str:
    """Normalize a user query before embedding and BM25 tokenisation.

    Steps:
    1. Normalize whitespace (same as _normalize_text).
    2. Lowercase for BM25 consistency.
    3. Remove punctuation that adds no retrieval signal.
    4. Truncate to max_chars.
    """
    q = _normalize_text(query or "")
    q = q.lower()
    q = re.sub(r"[^\w\s'-]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q[:max_chars]


def _sanitize_for_context(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Neutralize common prompt-injection markers and bound context size."""
    cleaned = html.unescape(text).replace("\x00", " ")
    cleaned = re.sub(r"(?i)```", "'''", cleaned)
    cleaned = re.sub(r"(?i)<\s*/?s*(script|iframe|object|embed)[^>]*>", "", cleaned)
    cleaned = re.sub(r"(?i)(system|developer|assistant)\s*:", r"\1 (quoted):", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:max_chars].rstrip() + ("…" if len(cleaned) > max_chars else "")


def _tokenize_for_bm25(text: str) -> list[str]:
    """Simple whitespace + punctuation tokeniser for BM25."""
    return [t for t in re.split(r"[\s\W]+", text.lower()) if len(t) > 1]


# ── Markdown-aware chunking ────────────────────────────────────────────────────


def _extract_headings(text: str) -> list[tuple[int, str]]:
    """Return a list of (level, heading_text) pairs found in *text* in order."""
    headings = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            headings.append((len(m.group(1)), m.group(2).strip()))
    return headings


def _split_by_markdown_headers(text: str) -> list[tuple[str | None, str]]:
    """Split *text* into (heading, section_body) pairs by top-level headings.

    Returns a list of tuples where:
    - ``heading`` is the text of the H1/H2 that precedes the section, or
      ``None`` for any content that precedes the first heading.
    - ``section_body`` is the raw text of that section (heading line included).

    This preserves the document hierarchy so each chunk knows which section
    it came from.
    """
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines(keepends=True):
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            if current_lines:
                sections.append((current_heading, "".join(current_lines).strip()))
            current_heading = m.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "".join(current_lines).strip()))

    return [(h, b) for h, b in sections if b]


def _chunk_text(
    text: str,
    max_chars: int = DEFAULT_CHUNK_SIZE,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Recursive paragraph-level chunker with character overlap.

    Strategy (from coarse to fine):
    1. Split on double newlines (paragraphs).
    2. If a paragraph fits in the current chunk, append it.
    3. If a paragraph alone exceeds max_chars, split it by sentences, then
       by fixed character windows as a last resort.
    4. Maintain an overlap tail from the previous chunk for context continuity.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            # Flush the current buffer first.
            if current:
                chunks.append(current.strip())
                current = ""
            # Try sentence-level split.
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            sent_buf = ""
            for sent in sentences:
                if len(sent) > max_chars:
                    # Last resort: fixed character windows.
                    if sent_buf:
                        chunks.append(sent_buf.strip())
                        sent_buf = ""
                    for start in range(0, len(sent), max_chars - overlap_chars):
                        part = sent[start : start + max_chars].strip()
                        if part:
                            chunks.append(part)
                elif len(sent_buf) + len(sent) + 1 > max_chars and sent_buf:
                    chunks.append(sent_buf.strip())
                    overlap = sent_buf[-overlap_chars:].strip() if overlap_chars else ""
                    sent_buf = f"{overlap} {sent}".strip() if overlap else sent
                else:
                    sent_buf = f"{sent_buf} {sent}".strip() if sent_buf else sent
            if sent_buf:
                chunks.append(sent_buf.strip())
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current.strip())
            overlap = current[-overlap_chars:].strip() if overlap_chars else ""
            current = f"{overlap}\n\n{paragraph}" if overlap else paragraph
        else:
            current = candidate

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]


# ── Document loading & chunk creation ─────────────────────────────────────────


def _load_documents(
    faq_dir: Path | None = None,
    max_document_chars: int | None = None,
) -> list[tuple[Path, str]]:
    """Load supported FAQ source files with explicit UTF-8 handling."""
    faq_dir = faq_dir or FAQ_DIR
    _max = max_document_chars if max_document_chars is not None else MAX_DOCUMENT_CHARS
    if not faq_dir.exists():
        raise RuntimeError(f"FAQ directory does not exist: {faq_dir}")

    documents: list[tuple[Path, str]] = []
    for path in sorted(p for p in faq_dir.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        text = _normalize_text(text)
        if not text:
            LOGGER.warning("Skipping empty FAQ document: %s", path)
            continue
        if len(text) > _max:
            raise ValueError(f"FAQ document too large ({len(text)} chars): {path}")
        documents.append((path, text))
    return documents


def _infer_tags(heading: str | None, text: str) -> list[str]:
    """Derive simple keyword tags from the heading and text for metadata."""
    tags: list[str] = []
    source_text = f"{heading or ''} {text}".lower()
    keyword_map = {
        "fraud": "fraud",
        "lost": "lost-card",
        "stolen": "lost-card",
        "lock": "card-lock",
        "unlock": "card-lock",
        "balance": "account",
        "transaction": "transactions",
        "statement": "account",
        "interest": "rates",
        "rate": "rates",
        "saving": "savings",
        "checking": "checking",
        "credit": "credit",
        "verification": "identity",
        "identity": "identity",
        "dispute": "dispute",
        "refund": "dispute",
        "replacement": "card-replacement",
    }
    for keyword, tag in keyword_map.items():
        if keyword in source_text and tag not in tags:
            tags.append(tag)
    return tags


def _document_chunks(
    faq_dir: Path | None = None,
    cfg: RAGConfig = DEFAULT_CONFIG,
) -> list[DocumentChunk]:
    """Create content-addressed chunks with rich metadata, skipping duplicates."""
    seen_chunk_hashes: set[str] = set()
    chunks: list[DocumentChunk] = []

    for path, text in _load_documents(faq_dir, max_document_chars=cfg.max_document_chars):
        doc_hash = _sha256(text)
        source = path.stem
        doc_headings = _extract_headings(text)
        top_heading = doc_headings[0][1] if doc_headings else source

        sections = _split_by_markdown_headers(text)
        global_chunk_index = 0

        for section_heading, section_body in sections:
            section_name = section_heading or top_heading
            section_chunks = _chunk_text(
                section_body,
                max_chars=cfg.chunk_size,
                overlap_chars=cfg.chunk_overlap,
            )

            for local_idx, chunk_text in enumerate(section_chunks):
                chunk_hash = _sha256(chunk_text)
                if chunk_hash in seen_chunk_hashes:
                    LOGGER.info("Skipping duplicate FAQ chunk from %s", path.name)
                    continue
                seen_chunk_hashes.add(chunk_hash)

                chunk_id = f"{source}:{global_chunk_index}:{chunk_hash[:12]}"
                tags = _infer_tags(section_heading, chunk_text)

                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        text=chunk_text,
                        metadata={
                            # ── Provenance ──────────────────────────────
                            "source": source,
                            "file_name": path.name,
                            "path": str(path.relative_to(path.parent.parent.parent)),
                            # ── Document structure ──────────────────────
                            "doc_heading": top_heading,
                            "section_name": section_name,
                            "chunk_index": global_chunk_index,
                            "section_chunk_index": local_idx,
                            # ── Content addressing ──────────────────────
                            "doc_hash": doc_hash,
                            "chunk_hash": chunk_hash,
                            # ── Discovery aids ──────────────────────────
                            "content_type": path.suffix.lower().lstrip("."),
                            "tags": ",".join(tags),
                        },
                    )
                )
                global_chunk_index += 1

    return chunks


# ── ChromaDB helpers ──────────────────────────────────────────────────────────


def _get_client(path: Path | None = None):
    path = path or CHROMA_PATH
    return chromadb.PersistentClient(path=str(path))


def _get_or_create_collection(client):
    return client.get_or_create_collection(COLLECTION_NAME, embedding_function=None)


def _reset_collection(client):
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        LOGGER.debug("Collection %s did not exist before rebuild", COLLECTION_NAME)
    return client.create_collection(COLLECTION_NAME, embedding_function=None)


# ── Index build / refresh ─────────────────────────────────────────────────────


def _build_index(
    rebuild: bool = False,
    faq_dir: Path | None = None,
    cfg: RAGConfig = DEFAULT_CONFIG,
) -> int:
    global _collection, _provider
    client = _get_client()
    _provider = get_default_provider()
    _collection = _reset_collection(client) if rebuild else _get_or_create_collection(client)

    chunks = _document_chunks(faq_dir=faq_dir, cfg=cfg)
    if not chunks:
        raise RuntimeError(f"No FAQ documents found in {faq_dir or FAQ_DIR}")

    current = _collection.get(include=["metadatas"])
    current_ids = set(current.get("ids", []))
    desired_ids = {chunk.chunk_id for chunk in chunks}

    # Remove stale chunks (documents deleted or content changed).
    stale_ids = list(current_ids - desired_ids)
    if stale_ids:
        _collection.delete(ids=stale_ids)
        LOGGER.info("faq_index_pruned_stale_chunks", extra={"count": len(stale_ids)})

    chunks_to_write = [chunk for chunk in chunks if rebuild or chunk.chunk_id not in current_ids]
    if chunks_to_write:
        embeddings = _provider.embed_batched([chunk.text for chunk in chunks_to_write])
        _collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks_to_write],
            documents=[chunk.text for chunk in chunks_to_write],
            metadatas=[chunk.metadata for chunk in chunks_to_write],
            embeddings=embeddings,
        )
        LOGGER.info(
            "faq_index_updated",
            extra={"upserted": len(chunks_to_write), "total": len(chunks)},
        )

    return len(chunks)


def _get_collection():
    global _collection, _provider
    if _collection is None:
        client = _get_client()
        _provider = get_default_provider()
        _collection = _get_or_create_collection(client)
        if _collection.count() == 0:
            _build_index()
    return _collection


def build_index(rebuild: bool = False) -> dict:
    """Build or incrementally refresh the FAQ vector index."""
    count = _build_index(rebuild=rebuild)
    return {"status": "indexed", "chunks": count, "collection": COLLECTION_NAME}


def rebuild_index() -> dict:
    """Force a clean rebuild of the FAQ vector index."""
    return build_index(rebuild=True)


# ── Similarity helpers ────────────────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _mmr_order(
    query_embedding: list[float],
    embeddings: list[list[float]],
    k: int,
    mmr_lambda: float = MMR_LAMBDA,
) -> list[int]:
    """Maximal Marginal Relevance — select *k* diverse, relevant results."""
    selected: list[int] = []
    candidates = set(range(len(embeddings)))
    while candidates and len(selected) < k:
        best_idx = max(
            candidates,
            key=lambda idx: (
                mmr_lambda * _cosine_similarity(query_embedding, embeddings[idx])
                - (1 - mmr_lambda)
                * max(
                    (_cosine_similarity(embeddings[idx], embeddings[j]) for j in selected),
                    default=0.0,
                )
            ),
        )
        selected.append(best_idx)
        candidates.remove(best_idx)
    return selected


# ── BM25 retrieval ─────────────────────────────────────────────────────────────


def _bm25_scores(
    query_tokens: list[str],
    all_texts: list[str],
) -> list[float]:
    """Return BM25 scores for *all_texts* against *query_tokens*.

    Returns a list of the same length as *all_texts*.  Returns zeros if
    rank_bm25 is not installed (graceful degradation to dense-only retrieval).
    """
    if not query_tokens:
        return [0.0] * len(all_texts)
    try:
        from rank_bm25 import BM25Okapi  # noqa: PLC0415

        corpus = [_tokenize_for_bm25(t) for t in all_texts]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)
        return list(scores)
    except ImportError:
        LOGGER.warning("rank_bm25 not installed; BM25 retrieval disabled")
        return [0.0] * len(all_texts)


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────────────


def _rrf_fuse(
    dense_indices: list[int],
    bm25_indices: list[int],
    n_total: int,
    dense_weight: float,
    bm25_weight: float,
    rrf_k: int,
) -> list[tuple[int, float]]:
    """Fuse dense and BM25 result lists via Reciprocal Rank Fusion.

    Args:
        dense_indices: Indices into the candidate pool, ordered by dense score.
        bm25_indices:  Indices into the candidate pool, ordered by BM25 score.
        n_total:       Total number of candidates in the pool.
        dense_weight:  Weight multiplier applied to the dense RRF contribution.
        bm25_weight:   Weight multiplier applied to the BM25 RRF contribution.
        rrf_k:         RRF smoothing constant (60 is the standard default).

    Returns:
        List of (index, fused_score) sorted by descending fused score.
    """
    scores: dict[int, float] = {i: 0.0 for i in range(n_total)}

    for rank, idx in enumerate(dense_indices):
        scores[idx] += dense_weight / (rrf_k + rank + 1)

    for rank, idx in enumerate(bm25_indices):
        scores[idx] += bm25_weight / (rrf_k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ── Public search entry point ──────────────────────────────────────────────────


def search_faq(
    query: str,
    k: int = 3,
    source: str | None = None,
    use_mmr: bool = True,
    cfg: RAGConfig = DEFAULT_CONFIG,
) -> dict:
    """Hybrid semantic + BM25 search over the FAQ/policy knowledge base.

    Retrieval pipeline:
    1. Normalize and embed the query.
    2. Dense vector search (ChromaDB) for ``k * mmr_fetch_multiplier`` candidates.
    3. BM25 sparse search over the same candidate pool.
    4. Reciprocal Rank Fusion of dense + BM25 rankings.
    5. MMR reranking for diversity (when ``use_mmr=True``).
    6. Sanitise and return top-k results with rich citations.

    Args:
        query:   User question or search phrase.
        k:       Number of results to return (capped at ``MAX_K``).
        source:  If provided, restrict results to chunks from this document stem.
        use_mmr: Apply MMR reranking for diversity (default True).
        cfg:     RAG configuration override (uses ``DEFAULT_CONFIG`` if omitted).

    Returns:
        ``{"results": [...]}`` where each result dict has:
        ``id``, ``source``, ``file_name``, ``section_name``, ``doc_heading``,
        ``chunk_index``, ``citation``, ``text``, ``distance``, ``tags``.
    """
    raw_query = _normalize_text(query or "")[: cfg.max_query_chars]
    if not raw_query:
        return {"results": [], "warning": "empty query"}

    k = max(1, min(int(k), cfg.max_k))

    collection = _get_collection()
    if collection.count() == 0:
        return {"results": [], "warning": "FAQ index is empty"}

    normalized_query = _normalize_query(raw_query, cfg.max_query_chars)
    query_embedding = _provider.embed([raw_query])[0]
    fetch_k = min(
        max(k * cfg.mmr_fetch_multiplier, k),
        collection.count(),
    )
    where = {"source": source} if source else None

    # ── Stage 1: Dense retrieval ──────────────────────────────────────────
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=fetch_k,
        where=where,
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    docs = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    raw_embeddings = results.get("embeddings", [[]])[0]
    embeddings = raw_embeddings.tolist() if hasattr(raw_embeddings, "tolist") else raw_embeddings
    ids = results.get("ids", [[]])[0]

    if not docs:
        return {"results": []}

    # ── Stage 2: BM25 over candidate pool ────────────────────────────────
    query_tokens = _tokenize_for_bm25(normalized_query)
    bm25_raw = _bm25_scores(query_tokens, docs)

    # Build rank lists for RRF (dense = original Chroma order; BM25 = sorted by score).
    dense_indices = list(range(len(docs)))  # already ranked by Chroma
    bm25_indices = sorted(range(len(docs)), key=lambda i: bm25_raw[i], reverse=True)

    # ── Stage 3: Reciprocal Rank Fusion ──────────────────────────────────
    fused = _rrf_fuse(
        dense_indices,
        bm25_indices,
        n_total=len(docs),
        dense_weight=cfg.dense_weight,
        bm25_weight=cfg.bm25_weight,
        rrf_k=cfg.rrf_k,
    )
    fused_indices = [idx for idx, _ in fused]

    # ── Stage 4: MMR reranking over fused order ───────────────────────────
    if use_mmr and len(embeddings) > 0:
        # MMR works on the fused ordering.
        order = _mmr_order(
            query_embedding,
            [embeddings[i] for i in fused_indices],
            k,
            mmr_lambda=cfg.mmr_lambda,
        )
        # Map back to original pool indices.
        final_indices = [fused_indices[i] for i in order]
    else:
        final_indices = fused_indices[:k]

    # ── Stage 5: Assemble results ─────────────────────────────────────────
    hits: list[dict] = []
    seen_hashes: set[str] = set()

    for idx in final_indices:
        meta = metadatas[idx] or {}
        chunk_hash = meta.get("chunk_hash") or _sha256(docs[idx])
        if chunk_hash in seen_hashes:
            continue
        seen_hashes.add(chunk_hash)

        section_name = meta.get("section_name", meta.get("source", "unknown"))
        chunk_index = meta.get("chunk_index", 0)

        hits.append(
            {
                "id": ids[idx],
                # ── Provenance ──────────────────────────────────────────
                "source": meta.get("source", "unknown"),
                "file_name": meta.get("file_name"),
                "doc_heading": meta.get("doc_heading"),
                "section_name": section_name,
                # ── Position ────────────────────────────────────────────
                "chunk_index": chunk_index,
                "section_chunk_index": meta.get("section_chunk_index", 0),
                # ── Citation (preserved backward-compat format + richer) ─
                "citation": f"{meta.get('source', 'unknown')}#{chunk_index}",
                "section_citation": (
                    f"{meta.get('source', 'unknown')} § {section_name} #{chunk_index}"
                ),
                # ── Content ─────────────────────────────────────────────
                "text": _sanitize_for_context(docs[idx], cfg.max_context_chars),
                "distance": round(float(distances[idx]), 4),
                "tags": [t for t in meta.get("tags", "").split(",") if t],
            }
        )
        if len(hits) >= k:
            break

    return {"results": hits}


# ── Script entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(build_index())
    print(search_faq("what happens if I lose my card"))
