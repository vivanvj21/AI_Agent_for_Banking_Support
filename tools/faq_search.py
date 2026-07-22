"""
FAQ / policy document search tool backed by a persistent Chroma collection.

The indexer is intentionally small, but production-oriented: it preserves
metadata, uses deterministic content-addressed chunk IDs, skips duplicate
chunks, supports incremental update/delete, and sanitizes retrieved context
before it is passed back to an LLM-facing agent.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import logging
import re
from pathlib import Path
from typing import Any

import chromadb

from tools.embeddings import get_default_provider

LOGGER = logging.getLogger(__name__)

FAQ_DIR = Path(__file__).parent.parent / "knowledge_base" / "faq_docs"
CHROMA_PATH = Path(__file__).parent.parent / "knowledge_base" / "chroma_store"
COLLECTION_NAME = "faq_docs"
SUPPORTED_SUFFIXES = {".md", ".txt"}
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 120
MAX_DOCUMENT_CHARS = 100_000
MAX_QUERY_CHARS = 1_000
MAX_CONTEXT_CHARS = 1_200
MAX_K = 10
MMR_FETCH_MULTIPLIER = 4
MMR_LAMBDA = 0.7

_collection = None
_provider = None


@dataclass(frozen=True)
class DocumentChunk:
    """A safely indexed text chunk with stable metadata."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    """Normalize text enough for stable hashing/indexing without losing content."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sanitize_for_context(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Neutralize common prompt-injection markers and bound context size."""
    cleaned = html.unescape(text).replace("\x00", " ")
    cleaned = re.sub(r"(?i)```", "'''", cleaned)
    cleaned = re.sub(r"(?i)<\s*/?\s*(script|iframe|object|embed)[^>]*>", "", cleaned)
    cleaned = re.sub(r"(?i)(system|developer|assistant)\s*:", r"\1 (quoted):", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:max_chars].rstrip() + ("…" if len(cleaned) > max_chars else "")


def _load_documents(faq_dir: Path | None = None) -> list[tuple[Path, str]]:
    """Load supported FAQ source files with explicit UTF-8 handling."""
    faq_dir = faq_dir or FAQ_DIR
    if not faq_dir.exists():
        raise RuntimeError(f"FAQ directory does not exist: {faq_dir}")

    documents: list[tuple[Path, str]] = []
    for path in sorted(
        p for p in faq_dir.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES
    ):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        text = _normalize_text(text)
        if not text:
            LOGGER.warning("Skipping empty FAQ document: %s", path)
            continue
        if len(text) > MAX_DOCUMENT_CHARS:
            raise ValueError(f"FAQ document too large ({len(text)} chars): {path}")
        documents.append((path, text))
    return documents


def _chunk_text(
    text: str,
    max_chars: int = DEFAULT_CHUNK_SIZE,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Chunk text by paragraphs with bounded character overlap for recall."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError(
            "overlap_chars must be non-negative and smaller than max_chars"
        )

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for start in range(0, len(paragraph), max_chars - overlap_chars):
                part = paragraph[start : start + max_chars].strip()
                if part:
                    chunks.append(part)
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
    return chunks


def _document_chunks(faq_dir: Path | None = None) -> list[DocumentChunk]:
    """Create content-addressed chunks while skipping duplicate chunk text."""
    seen_chunk_hashes: set[str] = set()
    chunks: list[DocumentChunk] = []

    for path, text in _load_documents(faq_dir):
        doc_hash = _sha256(text)
        source = path.stem
        for chunk_index, chunk in enumerate(_chunk_text(text)):
            chunk_hash = _sha256(chunk)
            if chunk_hash in seen_chunk_hashes:
                LOGGER.info("Skipping duplicate FAQ chunk from %s", path.name)
                continue
            seen_chunk_hashes.add(chunk_hash)
            chunk_id = f"{source}:{chunk_index}:{chunk_hash[:12]}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk,
                    metadata={
                        "source": source,
                        "path": str(path.relative_to(path.parent.parent.parent)),
                        "file_name": path.name,
                        "chunk_index": chunk_index,
                        "doc_hash": doc_hash,
                        "chunk_hash": chunk_hash,
                        "content_type": path.suffix.lower().lstrip("."),
                    },
                )
            )
    return chunks


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


def _build_index(rebuild: bool = False) -> int:
    global _collection, _provider
    client = _get_client()
    _provider = get_default_provider()
    _collection = (
        _reset_collection(client) if rebuild else _get_or_create_collection(client)
    )

    chunks = _document_chunks()
    if not chunks:
        raise RuntimeError(f"No FAQ documents found in {FAQ_DIR}")

    current = _collection.get(include=["metadatas"])
    current_ids = set(current.get("ids", []))
    desired_ids = {chunk.chunk_id for chunk in chunks}
    stale_ids = list(current_ids - desired_ids)
    if stale_ids:
        _collection.delete(ids=stale_ids)

    chunks_to_write = [
        chunk for chunk in chunks if rebuild or chunk.chunk_id not in current_ids
    ]
    if chunks_to_write:
        embeddings = _provider.embed_batched([chunk.text for chunk in chunks_to_write])
        _collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks_to_write],
            documents=[chunk.text for chunk in chunks_to_write],
            metadatas=[chunk.metadata for chunk in chunks_to_write],
            embeddings=embeddings,
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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _mmr_order(
    query_embedding: list[float], embeddings: list[list[float]], k: int
) -> list[int]:
    selected: list[int] = []
    candidates = set(range(len(embeddings)))
    while candidates and len(selected) < k:
        best_idx = max(
            candidates,
            key=lambda idx: (
                MMR_LAMBDA * _cosine_similarity(query_embedding, embeddings[idx])
                - (1 - MMR_LAMBDA)
                * max(
                    (
                        _cosine_similarity(embeddings[idx], embeddings[j])
                        for j in selected
                    ),
                    default=0.0,
                )
            ),
        )
        selected.append(best_idx)
        candidates.remove(best_idx)
    return selected


def search_faq(
    query: str, k: int = 3, source: str | None = None, use_mmr: bool = True
) -> dict:
    """Semantic search over the FAQ/policy knowledge base."""
    query = _normalize_text(query or "")[:MAX_QUERY_CHARS]
    if not query:
        return {"results": [], "warning": "empty query"}
    k = max(1, min(int(k), MAX_K))

    collection = _get_collection()
    if collection.count() == 0:
        return {"results": [], "warning": "FAQ index is empty"}

    query_embedding = _provider.embed([query])[0]
    fetch_k = min(max(k * MMR_FETCH_MULTIPLIER, k), collection.count())
    where = {"source": source} if source else None
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
    embeddings = (
        raw_embeddings.tolist() if hasattr(raw_embeddings, "tolist") else raw_embeddings
    )
    ids = results.get("ids", [[]])[0]

    order = (
        _mmr_order(query_embedding, embeddings, k)
        if use_mmr and len(embeddings) > 0
        else list(range(min(k, len(docs))))
    )
    hits = []
    seen_hashes: set[str] = set()
    for idx in order:
        meta = metadatas[idx] or {}
        chunk_hash = meta.get("chunk_hash") or _sha256(docs[idx])
        if chunk_hash in seen_hashes:
            continue
        seen_hashes.add(chunk_hash)
        hits.append(
            {
                "id": ids[idx],
                "source": meta.get("source", "unknown"),
                "file_name": meta.get("file_name"),
                "chunk_index": meta.get("chunk_index"),
                "citation": f"{meta.get('source', 'unknown')}#{meta.get('chunk_index', 0)}",
                "text": _sanitize_for_context(docs[idx]),
                "distance": round(float(distances[idx]), 4),
            }
        )
        if len(hits) >= k:
            break
    return {"results": hits}


if __name__ == "__main__":
    print(build_index())
    print(search_faq("what happens if I lose my card"))
