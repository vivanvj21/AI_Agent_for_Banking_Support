# Codebase Reference — Folder & Module Guide

> Every major folder and module explained: what it does, what it contains, and how it fits.

---

## Root

| File | Purpose |
|------|---------|
| `graph.py` | **Core orchestration.** LangGraph `StateGraph` defining all 10 graph nodes, conditional edges, and session helpers. The single entry point for all agent execution. |
| `config.py` | Runtime configuration and startup validation. `LLMProviderConfig`, `validate_startup()`, `require_llm_config()`. |
| `start.py` | Unified launcher (`cli`, `api`, `streamlit`, `check`, `init-db`). Auto-loads `.env`. |
| `cli.py` | Interactive terminal client. Full conversation loop with session resume, `--check-startup`, `--list-sessions`. |
| `app_streamlit.py` | Streamlit web UI. Session state management, chat display, sidebar verification. |
| `logging_config.py` | Configures structured JSON logging (stdout). Used by all modules. |
| `requirements.txt` | Python dependencies. Optional packages (`voyageai`, `mcp`, `langsmith`, `ragas`) are annotated. |
| `.env.example` | Template for all environment variables, grouped and annotated. |
| `docker-compose.yml` | Full-stack compose: `init` → `streamlit` + `api`, named volumes, health checks. |
| `docker-compose.dev.yml` | Dev overlay: mounts project dir into containers for hot reload. |

---

## `agents/`

The intelligence layer. Contains the supervisor, all three agents, and the Phase 8 orchestration modules.

| File | Role |
|------|------|
| `state.py` | `AgentState` TypedDict — the shared state passed through every LangGraph node. Contains messages, intent, routing_decision, memory_context, mcp_context, verification state. |
| `supervisor.py` | **Intelligent Supervisor.** 3-stage pipeline: keyword prefilter → LLM (`claude-haiku`) → composite confidence scoring. Returns `RoutingDecision`. |
| `registry.py` | **Agent Capability Registry.** `AgentCapability` dataclass for each agent. Contains intent labels, tool names, keyword hints, base confidence, priority. Queried by supervisor and MCP selector. |
| `confidence.py` | **Confidence Scoring Engine.** `compute_routing_decision()`, `get_fallback_decision()`, `RoutingDecision` dataclass. Defines `HIGH_CONFIDENCE`, `MEDIUM_CONFIDENCE`, etc. |
| `prompt_builder.py` | **Centralized Prompt Builder.** Single source of truth for all agent system prompts. Handles memory injection, RAG deduplication, token budgeting. |
| `orchestration_config.py` | **Routing Configuration.** `OrchestrationConfig` dataclass with all confidence thresholds and fallback rules. Fully env-overridable. |
| `collaborator.py` | **Multi-Agent Collaboration.** `detect_collaboration_need()`, `collaborate()`. Allows fraud agent to request search/account assistance. |
| `account_agent.py` | Account Agent. `run_account_agent()`. Tools: `get_balance`, `get_transaction_history`. Requires verification. |
| `fraud_agent.py` | Fraud & Security Agent. `run_fraud_agent()`. Tools: `lock_card`, `unlock_card`, `report_card_lost`, `report_fraud_transaction`, `get_flagged_transactions`. |
| `search_agent.py` | Search Agent. `run_search_agent()`. Tool: `search_faq`. No authentication required. |
| `verification.py` | Hard Python identity check. `try_verify()`, `extract_credentials()`. **Not an LLM-callable tool.** |

---

## `api/`

FastAPI REST application. Thin wrappers — no business logic reimplemented here.

| File | Role |
|------|------|
| `main.py` | App factory. `lifespan()` handles DB init, Chroma build, Memory init, MCP discovery, readiness signaling. CORS middleware. Router registration. |
| `routes.py` | Core endpoints: `/chat`, `/verify`, `/account/balance`, `/account/history`, `/fraud/lock-card`, `/fraud/report`, `/faq/search`, `/health`. |
| `mcp_routes.py` | MCP endpoints: `/mcp/status`, `/mcp/tools`, `/mcp/tools/{intent}`, `/mcp/call`. |
| `health.py` | Kubernetes-style probes: `/health/live` (always 200), `/health/ready` (200 after startup). |
| `schemas.py` | All Pydantic request/response models. Single source of truth for API contract. |
| `dependencies.py` | FastAPI dependencies: `get_graph()` (cached LangGraph app), `require_verified_user(session_id)`. |
| `metrics.py` | In-process request count + latency tracking. `/metrics` endpoint. |

---

## `memory/`

The Memory & Context Engine (Phase 6). Gives the assistant persistent long-term memory.

| File | Role |
|------|------|
| `manager.py` | `MemoryManager` façade. `get_context()` for retrieval, `record_turn()` for storage, `ensure_ready()` for init. `get_memory_manager()` singleton. |
| `models.py` | `MemoryFact`, `MemoryTurn`, `ContextPackage` dataclasses. |
| `store.py` | SQLite persistence layer. `MemoryStore`: stores facts, turns, summaries. |
| `semantic_store.py` | ChromaDB-backed semantic retrieval. `SemanticMemoryStore`: `index_turn()`, `search()`. |
| `retriever.py` | `MemoryRetriever`: combines SQL facts + semantic search. Deduplicates results. |
| `ranking.py` | `MemoryRanker`: recency + relevance scoring for fact prioritization. |
| `summarizer.py` | `MemorySummarizer`: LLM-based conversation summarization. Triggered at turn threshold. |
| `context_builder.py` | `ContextBuilder`: assembles `ContextPackage` with token budget. |

---

## `mcp_platform/`

MCP Platform Layer (Phase 9). Makes the assistant an extensible AI platform.

| File | Role |
|------|------|
| `__init__.py` | Public API — re-exports all key classes for clean imports. |
| `config.py` | `MCPPlatformConfig`, `MCPServerConfig`. Env-overridable settings for all 3 servers. |
| `registry.py` | `MCPRegistry`: in-memory catalog of servers and tools. Intent-based lookup, call metrics, status tracking. |
| `client.py` | `MCPClient`: stdio subprocess transport. Retry logic, timeout, normalized errors. `list_tools()` for auto-discovery. |
| `discovery.py` | `discover_all()`: queries each server's `list_tools()` at startup. Infers intent tags. Handles missing/unavailable servers. |
| `executor.py` | `ToolExecutor`: resolves server by tool name, executes, records metrics, feeds to Memory. Returns `ToolResult`. |
| `selector.py` | `ToolSelector`: confidence-gated intent → tool mapping. Returns `ToolInvocationPlan{should_invoke, tool_calls}`. |
| `manager.py` | `MCPManager` singleton façade. `plan_tool_calls()`, `execute_plan()`, `format_for_prompt()`. |

---

## `mcp_servers/`

FastMCP server scripts. Each runs as a standalone Python subprocess providing MCP-protocol tool access.

| File | Role |
|------|------|
| `account_server.py` | Exposes `get_balance`, `get_transaction_history` via MCP. Wraps `tools/account_tools.py`. |
| `faq_server.py` | Exposes `search_faq` via MCP. Wraps `tools/faq_search.py`. |
| `fraud_server.py` | Exposes `lock_card`, `unlock_card`, `report_card_lost`, `report_fraud_transaction`, `get_flagged_transactions` via MCP. |
| `common.py` | `safe_mcp_call()` helper: initializes DB, logs, handles errors consistently. |
| `test_client.py` | Manual test client for `account_server.py`. |
| `test_faq_client.py` | Manual test client for `faq_server.py`. |
| `test_fraud_client.py` | Manual test client for `fraud_server.py`. |

---

## `tools/`

Pure Python business logic functions. Called by agents and MCP servers. No LLM involvement.

| File | Role |
|------|------|
| `account_tools.py` | `verify_identity()` (Argon2), `get_balance()`, `get_transaction_history()`, `recall_previous_session()`. |
| `fraud_tools.py` | `lock_card()`, `unlock_card()`, `report_card_lost()`, `report_fraud_transaction()`, `get_flagged_transactions()`. |
| `faq_search.py` | `search_faq()` (BM25 + ChromaDB hybrid), `build_index()`. The RAG retrieval core. |
| `embeddings.py` | `EmbeddingProvider` abstract class. `SentenceTransformerProvider` (default) and `VoyageEmbeddingProvider` (optional). |
| `memory.py` | Session store: `create_session()`, `session_exists()`, `link_session_to_user()`, `append_message()`, `load_session_messages()`, `cleanup_old_sessions()`. |

---

## `db/`

Database initialization and schema.

| File | Role |
|------|------|
| `init_db.py` | `ensure_database()`: idempotent schema creation + optional demo data seeding. |
| `schema.sql` | SQLite DDL: `users`, `accounts`, `transactions`, `cards`, `sessions`, `session_messages`. |
| `seed_demo.py` | Inserts demo users (U1001/U1002/U1003) with Argon2-hashed PINs, accounts, transactions, cards. |

---

## `observability/`

LangSmith tracing and metadata utilities.

| File | Role |
|------|------|
| `langsmith_config.py` | `configure_langsmith()`: reads env vars, initializes LangSmith client. |
| `tracing.py` | `trace_node()` context manager: wraps graph node execution with LangSmith span. |
| `metadata.py` | `build_node_metadata()`: assembles consistent metadata dict for each span (session_id, turn, intent). |

---

## `evaluation/`

RAGAS evaluation harness.

| File | Role |
|------|------|
| `run_eval.py` | Main evaluation runner. Loads test cases, runs graph, scores with RAGAS. |
| `dataset.json` | Golden question/answer pairs for evaluation. |
| `ragas_config.py` | RAGAS metric configuration (faithfulness, answer_relevancy, context_precision). |

---

## `knowledge_base/`

FAQ and policy documents used to build the RAG index.

| Location | Content |
|----------|---------|
| `knowledge_base/faq_docs/` | Markdown files: account types, fraud procedures, card policies, interest rates, etc. |

**To add new knowledge:** Drop a `.md` or `.txt` file into `knowledge_base/faq_docs/`, then run:
```bash
python start.py init-db   # rebuilds the Chroma index
```

---

## `docs/`

Project documentation.

| File | Content |
|------|---------|
| `ARCHITECTURE.md` | High-level architecture, components, data flows |
| `SEQUENCE_DIAGRAMS.md` | Mermaid sequence diagrams for all major flows |
| `ADRs.md` | Architecture Decision Records |
| `API_REFERENCE.md` | Complete API endpoint reference |
| `DEVELOPER_GUIDE.md` | How to extend: agents, MCP servers, tools, memory, providers |
| `CONFIGURATION.md` | All environment variables and deployment options |
| `FOLDER_REFERENCE.md` | This file |
| `eval_results.md` | Latest RAGAS evaluation results |
| `rag_review.md` | RAG quality review notes |
| `architecture.svg` | Legacy architecture diagram |

---

## `docker/`

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: `builder` (gcc/g++ + pip install) → `runtime` (slim, non-root user) |

---

## `tests/`

Test suite using pytest.

```bash
pytest tests/ -v
```

| What is tested |
|---------------|
| Account tools (balance, history, verify) |
| Fraud tools (lock, unlock, report) |
| FAQ search (hybrid retrieval) |
| Graph routing (intent → agent) |
| Memory Engine (store, retrieval, summarization) |
| API endpoints (FastAPI TestClient) |
