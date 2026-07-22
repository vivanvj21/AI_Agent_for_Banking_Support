# RAG Pipeline Engineering Review

## Architecture Summary

The FAQ RAG pipeline loads Markdown and plain-text policy files from `knowledge_base/faq_docs`, normalizes UTF-8 text, chunks documents into overlapping paragraph-aware chunks, embeds chunks through the provider abstraction in `tools/embeddings.py`, and stores vectors in a persistent ChromaDB collection named `faq_docs`. Retrieval enters through `tools.faq_search.search_faq`, which embeds the query, retrieves candidate chunks from Chroma, optionally reorders them with maximal marginal relevance (MMR), sanitizes context, and returns bounded chunks with source metadata and citation IDs.

The LangGraph search path delegates general policy questions to `agents/search_agent.py`. The Search Agent must call `search_faq`, treats retrieved text as untrusted quoted reference material, and cites returned chunk identifiers. The same search function is exposed over MCP by `mcp_servers/faq_server.py`, so CLI/Streamlit/LangGraph and MCP access share one retrieval implementation.

Conversation memory is separate from the FAQ vector store. Session and long-term memory are stored in SQLite via `tools/memory.py`; retrieved FAQ chunks are not written into conversation memory by the retrieval layer.

## Problems Found

- Chunk IDs were positional (`source_index`) rather than content-addressed, making updates and duplicate handling brittle.
- Index rebuild deleted and recreated the collection every time, with no incremental refresh path.
- Document loading lacked explicit encoding, file-type allowlisting beyond Markdown globbing, oversized document safeguards, and duplicate chunk detection.
- Metadata only included a source stem, limiting filtering, citations, and auditability.
- Retrieval used raw top-k similarity only; it had no diversity reranking, source filtering, query bounds, empty-index handling, or duplicate-hit removal.
- Retrieved context was returned as a Python dictionary string to the LLM, with no prompt-injection framing or citation formatting.
- Tests did not cover FAQ indexing/retrieval failure modes.

## Risk Assessment

| Area | Risk Before | Risk After |
| --- | --- | --- |
| Prompt injection through retrieved Markdown | Medium | Lower: context is sanitized and framed as untrusted quoted text. |
| Duplicate vectors and stale chunks | Medium | Lower: content hashes, deterministic IDs, upsert, and stale deletion are in place. |
| Retrieval quality | Medium | Lower: larger overlapping chunks and MMR improve recall/diversity for FAQ-scale data. |
| Operational reliability | Medium | Lower: explicit UTF-8 loading, document-size limits, empty-query handling, and tests are added. |
| Open-source usability | Low | Low: local deterministic embeddings remain available when external API keys are absent. |

## Improvements Made

- Added UTF-8 document loading for `.md` and `.txt` FAQ files with empty-file skipping and oversized-document rejection.
- Replaced naive chunk IDs with stable content-addressed IDs derived from SHA-256 chunk hashes.
- Preserved metadata for source, relative path, file name, chunk index, document hash, chunk hash, and content type.
- Added incremental indexing with Chroma `upsert` and stale-vector deletion, plus explicit clean rebuild support.
- Added duplicate chunk detection at indexing time and duplicate result suppression at retrieval time.
- Added bounded query length, top-k clamping, optional source metadata filtering, MMR reranking, and empty-index/empty-query handling.
- Added context sanitization for common prompt-injection markers, malicious HTML tags, code fences, null bytes, and oversized retrieved chunks.
- Updated the Search Agent prompt and tool-result formatting to treat retrieved text as untrusted quoted context and require citations.
- Extended the MCP FAQ tool with source filtering to match the core retrieval API.
- Added automated FAQ retrieval/indexing tests.

## Performance Notes

- Embeddings are now batched via the provider abstraction, reducing API-call pressure for larger FAQ sets.
- Incremental indexing avoids recomputing embeddings for unchanged chunk IDs.
- Retrieval fetches a bounded candidate set (`k * 4`, capped by collection size) before MMR, which is appropriate for the current small FAQ corpus.
- Query and context length caps reduce token and memory overhead.

## Suggested Future Enhancements

- Add a stronger open-source embedding option such as `BAAI/bge-small-en-v1.5` or `intfloat/e5-small-v2` through `sentence-transformers` for local semantic quality, while keeping the current dependency-light fallback for CI.
- Add hybrid lexical + vector retrieval if the FAQ corpus grows or policy identifiers become important.
- Add offline retrieval evaluation fixtures with precision@k / recall@k metrics for canonical banking questions.
- Add a scheduled indexing command that reports added, updated, deleted, and duplicate chunks.
- Add metadata filters for policy category, jurisdiction, effective date, and document version if the document set becomes regulated content.
