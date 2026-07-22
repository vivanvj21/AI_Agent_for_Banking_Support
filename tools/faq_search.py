"""
FAQ / policy document search tool, backed by a persistent Chroma collection.
Embeddings come from tools.embeddings.get_default_provider() — Voyage AI in
production, a local deterministic fallback for offline dev (see embeddings.py
for why this split exists and what the tradeoff is).
"""

from pathlib import Path
import chromadb
from tools.embeddings import get_default_provider

FAQ_DIR = Path(__file__).parent.parent / "knowledge_base" / "faq_docs"
CHROMA_PATH = Path(__file__).parent.parent / "knowledge_base" / "chroma_store"

_collection = None
_provider = None


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Naive paragraph-based chunking — fine for short FAQ docs like ours."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) > max_chars and current:
            chunks.append(current.strip())
            current = p
        else:
            current += "\n\n" + p if current else p
    if current:
        chunks.append(current.strip())
    return chunks


def _build_index():
    global _collection, _provider
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    _provider = get_default_provider()

    # Rebuild fresh each time build_index() is explicitly called; otherwise reuse.
    try:
        client.delete_collection("faq_docs")
    except Exception:
        pass
    _collection = client.create_collection("faq_docs", embedding_function=None)

    ids, docs, metadatas = [], [], []
    for path in sorted(FAQ_DIR.glob("*.md")):
        text = path.read_text()
        for i, chunk in enumerate(_chunk_text(text)):
            ids.append(f"{path.stem}_{i}")
            docs.append(chunk)
            metadatas.append({"source": path.stem})

    if not docs:
        raise RuntimeError(f"No FAQ documents found in {FAQ_DIR}")

    embeddings = _provider.embed(docs)
    _collection.add(ids=ids, documents=docs, metadatas=metadatas, embeddings=embeddings)
    return len(docs)


def _get_collection():
    global _collection, _provider
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _provider = get_default_provider()
        try:
            _collection = client.get_collection("faq_docs", embedding_function=None)
        except Exception:
            # Not built yet — build it now.
            _build_index()
    return _collection


def build_index() -> dict:
    """Explicit (re)build of the FAQ vector index. Call this once at setup / after doc changes."""
    n = _build_index()
    return {"status": "indexed", "chunks": n}


def search_faq(query: str, k: int = 3) -> dict:
    """
    Semantic search over the FAQ/policy knowledge base.
    Returns top-k chunks with their source doc name.
    """
    collection = _get_collection()
    query_embedding = _provider.embed([query])[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=k)

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append({"source": meta["source"], "text": doc, "distance": round(dist, 4)})
    return {"results": hits}


if __name__ == "__main__":
    print(build_index())
    print(search_faq("what happens if I lose my card"))
