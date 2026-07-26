"""
Memory Engine — providers sub-package.

Currently the only provider is the built-in SQLite+Chroma backend
(implemented in memory/store.py and memory/semantic_store.py).

Future providers (Redis, Postgres, Pinecone, etc.) can be added here
and wired via MEMORY_BACKEND env var without changing any agent code.
"""
