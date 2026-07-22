"""
Embedding provider abstraction for the FAQ search tool.

Why an abstraction instead of hardcoding one embedding call: Anthropic does not
offer its own embeddings endpoint, so any Claude-based RAG system in
production needs a separate embeddings provider. Voyage AI is Anthropic's
recommended embeddings partner and is the intended default here.

For local/offline development (e.g. no network access to an embeddings API),
LocalHashEmbeddingProvider gives a deterministic, dependency-free dense vector
so the rest of the pipeline (Chroma storage, cosine retrieval, RAGAS-style
eval) can be built and tested end-to-end without a paid API call. It is
explicitly NOT a production embedding — it's a fixed random projection of a
bag-of-words vector, seeded for determinism, good for demoing plumbing but not
for real semantic search quality. Swap in VoyageEmbeddingProvider (or an
OpenAI/Cohere provider) for anything beyond local development.
"""

from abc import ABC, abstractmethod
import hashlib
import os
import sys
import numpy as np


class EmbeddingProvider(ABC):
    """Minimal embedding provider interface used by the RAG pipeline."""

    model_name: str = "unknown"
    dimensions: int | None = None

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        raise NotImplementedError

    def embed_batched(
        self, texts: list[str], batch_size: int = 64
    ) -> list[list[float]]:
        """Embed texts in bounded batches to avoid provider request limits."""
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            embeddings.extend(self.embed(texts[start : start + batch_size]))
        return embeddings


class VoyageEmbeddingProvider(EmbeddingProvider):
    """
    Production provider. Requires VOYAGE_API_KEY and network access to
    api.voyageai.com. Uses voyage-3.5 (or override via VOYAGE_MODEL env var).
    """

    def __init__(self, model: str | None = None):
        try:
            import voyageai
        except ImportError as e:
            raise ImportError(
                "voyageai package not installed. Run: pip install voyageai"
            ) from e
        api_key = os.environ.get("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError("VOYAGE_API_KEY environment variable is not set.")
        self.client = voyageai.Client(api_key=api_key)
        self.model = model or os.environ.get("VOYAGE_MODEL", "voyage-3.5")
        self.model_name = self.model
        # voyage-3.5 currently returns 1024-dimensional vectors. Keep this
        # as metadata only so model overrides do not break runtime behavior.
        self.dimensions = 1024 if self.model == "voyage-3.5" else None

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self.client.embed(texts, model=self.model, input_type="document")
        return result.embeddings


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """
    Offline fallback for local development and CI, where no external
    embeddings API is reachable. Deterministic, dependency-free.

    Method: hash each token into a fixed-size vocabulary bucket (hashing
    trick), weight by term frequency, then apply a fixed random orthogonal-ish
    projection (seeded) down to `dim` dimensions to get a dense vector. This
    captures crude lexical overlap only — it is NOT a semantic embedding, and
    should be clearly labeled as a dev/test stand-in in any README or demo.
    """

    def __init__(self, dim: int = 256, vocab_buckets: int = 4096, seed: int = 42):
        self.dim = dim
        self.dimensions = dim
        self.model_name = f"local-hash-{dim}"
        self.vocab_buckets = vocab_buckets
        rng = np.random.default_rng(seed)
        self.projection = rng.normal(size=(vocab_buckets, dim))

    def _tokenize(self, text: str) -> list[str]:
        return [
            t
            for t in "".join(c.lower() if c.isalnum() else " " for c in text).split()
            if t
        ]

    def _bow_vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.vocab_buckets)
        for token in self._tokenize(text):
            bucket = (
                int(hashlib.md5(token.encode()).hexdigest(), 16) % self.vocab_buckets
            )
            vec[bucket] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            bow = self._bow_vector(text)
            dense = bow @ self.projection
            norm = np.linalg.norm(dense)
            dense = dense / norm if norm > 0 else dense
            out.append(dense.tolist())
        return out


def get_default_provider() -> EmbeddingProvider:
    """
    Selects Voyage if VOYAGE_API_KEY is set and the package is importable,
    otherwise falls back to the local provider with a clear stderr warning.
    """
    if os.environ.get("VOYAGE_API_KEY"):
        try:
            return VoyageEmbeddingProvider()
        except Exception as e:
            print(
                f"[embeddings] Voyage provider unavailable ({e}); falling back to local dev embeddings.",
                file=sys.stderr,
            )
    else:
        print(
            "[embeddings] VOYAGE_API_KEY not set; using LocalHashEmbeddingProvider (dev/demo only, not semantic).",
            file=sys.stderr,
        )
    return LocalHashEmbeddingProvider()
