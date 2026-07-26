# Changelog

All notable changes to this project are documented here.

---

## [Phase 10] — 2026-07-26 — Documentation & Repository Polish

### Added
- `docs/ARCHITECTURE.md` — High-level architecture with Mermaid component diagram, component tables, all data flows (request lifecycle, memory, RAG, MCP), and deployment diagram
- `docs/SEQUENCE_DIAGRAMS.md` — 6 Mermaid sequence/state diagrams (search flow, auth flow, collaboration, memory write, MCP execution, conversation lifecycle)
- `docs/ADRs.md` — 10 Architecture Decision Records covering every major technical decision
- `docs/API_REFERENCE.md` — Complete reference for all 15 API endpoints with request/response schemas, examples, and curl walkthroughs
- `docs/DEVELOPER_GUIDE.md` — Step-by-step guides for adding agents, MCP servers, tools, extending memory, and changing providers
- `docs/CONFIGURATION.md` — Complete environment variable reference with tuning guidance and `.env` template
- `docs/FOLDER_REFERENCE.md` — Every major folder and module documented
- `CONTRIBUTING.md` — Development setup, code style, branch strategy, and PR process
- `CHANGELOG.md` — This file

### Improved
- `README.md` — Complete rewrite: badges, Mermaid diagrams, feature tables, tech stack, installation, quick start, API reference, Docker, LangSmith setup, roadmap

---

## [Phase 9] — 2026-07-26 — Enterprise MCP & External Integrations

### Added
- `mcp_platform/` package: `config.py`, `registry.py`, `client.py`, `discovery.py`, `executor.py`, `selector.py`, `manager.py`
- `api/mcp_routes.py` — `/mcp/status`, `/mcp/tools`, `/mcp/tools/{intent}`, `/mcp/call`
- `MCPManager` singleton with lazy initialization and auto tool discovery
- `ToolInvocationPlan` — confidence-gated, intent-filtered tool selection
- `ToolResult` — normalized result format with `to_prompt_text()`, memory feed

### Modified
- `graph.py` — Added `mcp_tool_node` between `memory` and routing
- `agents/state.py` — Added `mcp_context: str | None`
- `api/main.py` — MCP platform initialization in `lifespan()`, registered `mcp_router`

---

## [Phase 8] — 2026-07-25 — Intelligent Orchestration Layer

### Added
- `agents/registry.py` — `AgentCapability` registry with intent/tool/confidence descriptors
- `agents/confidence.py` — Composite confidence scoring: keyword × LLM × context
- `agents/prompt_builder.py` — Centralized prompt construction with memory injection and token budgeting
- `agents/orchestration_config.py` — Env-driven routing thresholds and fallback rules
- `agents/collaborator.py` — Multi-agent collaboration (fraud → search, fraud → account)

### Modified
- `agents/supervisor.py` — Complete rewrite: 3-stage classification (keyword prefilter → LLM → composite score)
- `agents/state.py` — Added `routing_decision`, `recent_intents`, `fallback_attempts`, `mcp_context`
- `agents/account_agent.py` — Added `system_prompt_override` parameter
- `agents/fraud_agent.py` — Added `system_prompt_override` parameter
- `agents/search_agent.py` — Added `system_prompt_override` parameter
- `graph.py` — New `supervisor_node` with confidence routing, multi-agent collaboration in `fraud_agent_node`

---

## [Phase 7] — 2026-07-25 — Deployment & Production Readiness

### Added
- `docker/Dockerfile` — Multi-stage build (builder + slim runtime, non-root user, healthcheck)
- `docker-compose.yml` — Full stack: init, streamlit, api with named volumes and health checks
- `docker-compose.dev.yml` — Dev overlay with hot-reload volume mounts
- `start.py` — Unified launcher: `cli`, `api`, `streamlit`, `check`, `init-db`, `worker`
- `deploy.sh` / `deploy.bat` — Helper scripts for Linux/Windows
- `api/health.py` — `/health/live` (liveness) + `/health/ready` (readiness) probes
- `.dockerignore`

### Modified
- `api/main.py` — CORS middleware, root `/` endpoint, health router, readiness signaling
- `.env.example` — Complete rewrite covering all 6 phases
- `requirements.txt` — Added `python-dotenv`

---

## [Phase 6] — 2026-07-25 — Memory & Context Engine

### Added
- `memory/` package: `models.py`, `store.py`, `ranking.py`, `semantic_store.py`, `retriever.py`, `summarizer.py`, `context_builder.py`, `manager.py`
- `MemoryManager` façade with `get_context()` and `record_turn()`
- Long-term fact storage (SQLite) + semantic retrieval (ChromaDB)
- Token-budgeted context injection
- LLM-based conversation summarization

### Modified
- `graph.py` — Added `memory_node` between supervisor and routing
- `agents/state.py` — Added `memory_context`
- `agents/account_agent.py` — Memory context injection into system prompt

---

## [Phase 5] — AI Platform Layer

### Added
- `observability/` — LangSmith tracing: `langsmith_config.py`, `tracing.py`, `metadata.py`
- `evaluation/` — RAGAS evaluation harness

---

## [Phase 4] — RAGAS Evaluation

### Added
- `evaluation/run_eval.py` — Automated RAGAS scoring
- `docs/eval_results.md` — Evaluation results

---

## [Phase 3] — LangSmith Observability

### Added
- LangSmith `configure_langsmith()`, `trace_node()` context manager
- Span metadata: session_id, turn, intent, node

---

## [Phase 2] — Enterprise Hybrid RAG

### Added
- BM25 sparse retrieval (`rank-bm25`)
- Reciprocal Rank Fusion for hybrid scoring
- `EmbeddingProvider` abstraction with SentenceTransformer + VoyageAI backends
- Prompt injection defense in search agent system prompt

---

## [Phase 1] — Production Hardening

### Added
- LangGraph `StateGraph` with 9 nodes and conditional edges
- Hard verification gate (Python, not LLM-callable)
- 3 specialized agents: Search, Account, Fraud
- ChromaDB vector store + FAQ index
- SQLite schema with Argon2 PIN hashing
- FastAPI REST API with Pydantic schemas
- Streamlit web UI
- Interactive CLI with session persistence
- Structured JSON logging
- `validate_startup()` for configuration validation
