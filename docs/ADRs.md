# Architecture Decision Records

> This document captures the key architectural decisions made across all 10 development phases.
> Each ADR follows the standard format: Context → Decision → Rationale → Consequences.

---

## ADR-001: Provider Architecture — Anthropic Claude as Primary LLM

**Status:** Accepted  
**Phase:** 1 (Production Hardening)

### Context
The project requires an LLM for intent classification, tool selection, and response generation. Multiple providers exist (OpenAI, Anthropic, Google, local models). A provider abstraction was needed.

### Decision
Use **Anthropic Claude** as the sole LLM provider, with a `LLMProviderConfig` dataclass that supports future provider swapping via the `LLM_PROVIDER` env variable.

### Rationale
- Claude has excellent tool-use capability (critical for ReAct agents)
- Extended context window reduces truncation in multi-turn conversations
- `claude-haiku-4-5` is fast + cheap for classification; `claude-sonnet-4-5` for reasoning
- Using two model tiers (haiku for supervisor, sonnet for agents) cuts classification costs ~10×

### Consequences
- ✅ All agents have strong tool-use reliability
- ✅ Dual-tier model strategy reduces API cost
- ⚠️ Hard dependency on Anthropic API (no local fallback)
- ⚠️ Requires `ANTHROPIC_API_KEY` — no degraded mode without it

---

## ADR-002: LangGraph for Multi-Agent Orchestration

**Status:** Accepted  
**Phase:** 1 (Production Hardening)

### Context
Multi-agent systems require explicit state management, routing logic, and cycle prevention. Raw Python loops or chains are difficult to test, visualize, or extend.

### Decision
Use **LangGraph** (`StateGraph`) as the orchestration framework with a `TypedDict`-based `AgentState`.

### Rationale
- Explicit graph with named nodes makes routing auditable
- `TypedDict` state is easy to serialize, log, and test
- Conditional edges enforce the verification gate without LLM involvement
- LangSmith integrates directly with LangGraph for full trace visibility

### Consequences
- ✅ Routing is deterministic and testable
- ✅ State is fully serializable (used by eval harness and API)
- ✅ Adding new nodes requires only a function + edge — no refactoring
- ⚠️ Adds a non-trivial dependency; team must understand LangGraph concepts

---

## ADR-003: Hard Verification Gate (Not LLM-Callable)

**Status:** Accepted  
**Phase:** 1 (Production Hardening)

### Context
Account and fraud operations require identity verification. A naive implementation would make the verification check an LLM-callable tool or instruct the agent via prompt to "verify before proceeding."

### Decision
Identity verification is implemented as a **deterministic Python function** (`verify_gate_node`) that runs as a hard graph edge *before* account/fraud agents are invoked. It is **never** exposed as an LLM-callable tool.

### Rationale
- An LLM can be "argued out of" a prompt-level verification check via prompt injection
- A Python graph edge cannot be bypassed by manipulating conversation text
- The blast radius argument: even if the supervisor is compromised, it cannot call account tools — it can only route

### Consequences
- ✅ Prompt injection cannot bypass authentication
- ✅ Verification logic is independently testable
- ✅ Simple and auditable — no LLM involved in security-critical path
- ⚠️ Demo uses free-text PIN parsing (regex); production requires a structured login form

---

## ADR-004: Hybrid RAG — BM25 + Vector Search

**Status:** Accepted  
**Phase:** 2 (Enterprise Hybrid RAG)

### Context
Pure vector search misses exact keyword matches (e.g. "NEFT limit", "ATM PIN"). Pure BM25 misses semantic similarity. A hybrid approach is needed.

### Decision
Implement **Hybrid RAG** combining:
- **BM25** (`rank-bm25`) for sparse keyword retrieval
- **ChromaDB** for dense vector retrieval
- **Reciprocal Rank Fusion** for score merging and re-ranking

### Rationale
- BM25 + vector fusion is the industry-standard approach for high-precision retrieval
- ChromaDB is lightweight and embeds well in a Python process (no external vector DB server)
- `SentenceTransformer` for free local embeddings; `VoyageAI` as a drop-in upgrade

### Consequences
- ✅ Better recall for both keyword-heavy and semantic queries
- ✅ Pluggable embedding providers via `EmbeddingProvider` abstract class
- ✅ BM25 index built in-memory at startup; zero external dependency
- ⚠️ Two retrieval passes per query adds latency (~50ms)
- ⚠️ BM25 index is rebuilt on restart (no persistence)

---

## ADR-005: Memory Engine — SQLite + ChromaDB Dual Store

**Status:** Accepted  
**Phase:** 6 (Memory & Context Engine)

### Context
The assistant needs to remember user preferences, prior conversation context, and facts across sessions. This is not achievable with in-memory state alone.

### Decision
Implement a **dual-store Memory Engine**:
- **SQLite** (`memory_turns`, `memory_facts`, `memory_summaries`) for structured persistence
- **ChromaDB** (separate collection) for semantic similarity search over facts
- **LLM summarization** when turn count exceeds threshold

### Rationale
- SQLite is already present in the stack (accounts DB) — no new infrastructure
- Semantic search over long-term facts requires embeddings, which ChromaDB handles
- Summarization prevents unbounded token growth while preserving key context
- Token-budgeted injection keeps agent prompts within Claude's context window

### Consequences
- ✅ Persistent memory survives process restarts
- ✅ Semantic retrieval surfaces relevant past context even without exact keywords
- ✅ Token budget prevents runaway prompt inflation
- ⚠️ Two databases to back up (SQLite + ChromaDB)
- ⚠️ Summarization adds LLM cost when triggered

---

## ADR-006: Confidence-Based Routing (Phase 8)

**Status:** Accepted  
**Phase:** 8 (Intelligent Orchestration)

### Context
The original supervisor was a single LLM call that returned a bare `intent` string with no confidence signal. This made it impossible to implement fallback logic or detect ambiguous queries.

### Decision
Replace simple routing with a **3-stage confidence pipeline**:
1. Keyword prefilter (zero LLM cost, skips LLM for obvious cases)
2. LLM classification with explicit confidence + reasoning
3. Composite score: `0.65×LLM + 0.25×keyword + 0.10×context`

Route confidence tiers: `HIGH ≥ 0.75`, `MEDIUM ≥ 0.50`, `LOW ≥ 0.30`, `FALLBACK < 0.20`.

### Rationale
- The keyword prefilter eliminates an LLM call for ~40% of obvious queries
- Composite confidence is more stable than LLM confidence alone
- Fallback threshold prevents routing ambiguous queries to wrong agents
- `RoutingDecision` is logged and stored in state for debugging

### Consequences
- ✅ Faster routing for unambiguous queries (keyword prefilter path)
- ✅ Structured fallback chain for low-confidence turns
- ✅ `routing_decision` stored in state enables post-hoc analysis
- ⚠️ Composite formula weights are hardcoded; production should tune from eval data
- ⚠️ Supervisor uses `claude-haiku-4-5` — model name must be kept in sync with Anthropic releases

---

## ADR-007: MCP Platform — Subprocess Stdio Transport

**Status:** Accepted  
**Phase:** 9 (Enterprise MCP)

### Context
The MCP servers already existed as FastMCP scripts (`mcp_servers/*.py`). Integrating them into the agent loop required a client layer. Two options: (a) import the tools directly, (b) call them via MCP protocol.

### Decision
Use the **official MCP Python SDK** with **stdio subprocess transport**. Each tool call spawns a Python subprocess, communicates via stdin/stdout, and terminates after the call.

### Rationale
- Maintains clean separation: MCP servers can be replaced without touching agent code
- Subprocess isolation prevents MCP server crashes from killing the main process
- Any MCP-compatible client (Claude Desktop, external agents) can call the same servers
- `list_tools()` enables automatic tool discovery — no hardcoded registrations

### Consequences
- ✅ True MCP protocol compliance — interoperable with any MCP client
- ✅ Server isolation via subprocess
- ✅ Zero-config extensibility — adding a new `@mcp.tool()` auto-discovers
- ⚠️ Subprocess spawn per call adds ~200-500ms latency
- ⚠️ High-traffic scenarios would benefit from connection pooling (future work)
- ⚠️ `asyncio.run()` inside a sync FastAPI handler is suboptimal (but correct)

---

## ADR-008: Agent Capability Registry

**Status:** Accepted  
**Phase:** 8 (Intelligent Orchestration)

### Context
The supervisor needed to know which agent handles which intents, what tools each agent has, and what confidence to assign. This logic was previously embedded implicitly.

### Decision
Introduce an **explicit `AgentCapability` registry** (`agents/registry.py`) where each agent self-describes its:
- Supported intents and tools
- Keyword hints for the prefilter
- Base confidence score
- Priority for tie-breaking
- `requires_verification` flag

### Rationale
- Centralizes routing intelligence in one place
- Adding a new agent requires only a new `AgentCapability` entry + a run function
- Registry is queryable by the supervisor, MCP selector, and collaborator
- Eliminates string comparisons scattered across routing logic

### Consequences
- ✅ Single source of truth for agent capabilities
- ✅ New agents require minimal changes to supervisor or routing
- ✅ Registry snapshot exposed via `/mcp/status` for observability
- ⚠️ Registry is static (Python-level); dynamic registration from config not yet supported

---

## ADR-009: Centralized Prompt Builder

**Status:** Accepted  
**Phase:** 8 (Intelligent Orchestration)

### Context
Before Phase 8, each agent built its own system prompt ad-hoc. Memory context was assembled differently in each agent, making it hard to ensure consistency, token budgeting, or deduplication.

### Decision
Introduce a **centralized `prompt_builder.py`** module as the single source of truth for all agent system prompts. All prompts flow through:
1. Base agent prompt (canonical, in `prompt_builder.py`)
2. Memory context injection (token-budgeted, deduplicated)
3. RAG context injection (deduplicated chunks)
4. Conversation history trimming

Agents accept a `system_prompt_override` parameter for injection by the graph.

### Consequences
- ✅ Consistent prompt construction across all agents
- ✅ Deduplication and token budgeting in one place
- ✅ Backward compatible — agents fall back to their internal prompt if no override
- ⚠️ Prompt content is centralized but not versioned; changes affect all agents simultaneously

---

## ADR-010: Docker Multi-Stage Build + Named Volumes

**Status:** Accepted  
**Phase:** 7 (Deployment)

### Context
The application requires C/C++ build dependencies (`gcc`, `g++`) for some Python packages but the runtime image should be lean. Data (SQLite, ChromaDB) must survive container restarts.

### Decision
Use a **multi-stage Docker build** (builder stage with build tools → slim runtime image) and **named Docker volumes** for all persistent data.

### Rationale
- Multi-stage build reduces final image size by ~400MB
- Named volumes survive `docker compose down/up` cycles
- One-shot `init` service seeds demo data before Streamlit/API start
- Non-root user in runtime image for security hygiene

### Consequences
- ✅ Production-grade container image
- ✅ Data persists across deployments
- ✅ `docker compose up --build` is the single command to run the full stack
- ⚠️ `asyncio.run()` in FastAPI handlers is safe but not idiomatic async
