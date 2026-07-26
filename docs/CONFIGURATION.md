# Configuration Guide

> Complete reference for all environment variables, configuration options, and deployment settings.

---

## Quick Start

```bash
cp .env.example .env
# Edit .env — at minimum, set ANTHROPIC_API_KEY
```

---

## Core Configuration

### LLM Provider

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `ANTHROPIC_API_KEY` | — | **Yes** | Anthropic API key for Claude |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | No | Model used by agents for response generation |
| `LLM_PROVIDER` | `anthropic` | No | LLM provider. Currently only `anthropic` supported. |

---

## Observability Configuration

### LangSmith Tracing

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGSMITH_TRACING` | `false` | Set `true` to enable LangSmith distributed tracing |
| `LANGSMITH_API_KEY` | — | LangSmith API key (required if tracing enabled) |
| `LANGSMITH_PROJECT` | `banking-assistant` | Project name in LangSmith |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | LangSmith API endpoint |

**Usage:**
```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls__your_key_here
LANGSMITH_PROJECT=banking-assistant-prod
```

---

## Memory Engine Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_DB_PATH` | `db/memory.db` | Path to Memory Engine SQLite database |
| `MEMORY_MAX_TOKENS` | `1200` | Max token budget for memory context injection |
| `MEMORY_MAX_FACTS` | `8` | Max long-term facts to inject per turn |
| `MEMORY_SUMMARY_THRESHOLD` | `10` | Number of turns after which summarization is triggered |
| `MEMORY_SEMANTIC_ENABLED` | `true` | Enable ChromaDB semantic fact retrieval |

---

## RAG Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_DB_PATH` | `db/chroma_data` | Path to ChromaDB vector store |
| `EMBEDDING_PROVIDER` | `sentence_transformer` | Embedding provider. Options: `sentence_transformer`, `voyage` |
| `VOYAGE_API_KEY` | — | VoyageAI API key (required if `EMBEDDING_PROVIDER=voyage`) |
| `VOYAGE_MODEL` | `voyage-2` | VoyageAI model to use for embeddings |
| `RAG_CHUNK_SIZE` | `512` | Character size for document chunks |
| `RAG_CHUNK_OVERLAP` | `50` | Overlap between adjacent chunks |
| `RAG_TOP_K` | `3` | Number of results to retrieve |
| `RAG_HYBRID_ALPHA` | `0.5` | BM25 vs. vector weight (0=pure BM25, 1=pure vector) |

---

## Orchestration / Routing Configuration (Phase 8)

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCH_HIGH_CONF` | `0.75` | Confidence threshold for direct high-confidence routing |
| `ORCH_MED_CONF` | `0.50` | Medium confidence threshold |
| `ORCH_LOW_CONF` | `0.30` | Low confidence threshold (may trigger fallback) |
| `ORCH_FALLBACK_CONF` | `0.20` | Below this → clarify rather than route |
| `ORCH_MAX_FALLBACKS` | `2` | Maximum fallback agent attempts per turn |
| `ORCH_ENABLE_COLLAB` | `true` | Allow multi-agent collaboration |
| `ORCH_MAX_CTX_TOKENS` | `3000` | Maximum tokens for assembled context |
| `ORCH_MAX_HISTORY_TURNS` | `10` | How many past turns to include in conversation history |
| `ORCH_MAX_RAG_CHUNKS` | `5` | Maximum RAG chunks to inject per turn |
| `ORCH_MAX_MEMORY_FACTS` | `8` | Maximum memory facts to inject per turn |
| `ORCH_SUPERVISOR_MODEL` | `claude-haiku-4-5` | Model used for intent classification (cheap) |

**Tuning guidance:**

- **Lower `ORCH_FALLBACK_CONF`** → more turns go to agents (less "I'm not sure" responses, but more misdirected turns)
- **Raise `ORCH_HIGH_CONF`** → more turns go via the keyword prefilter (cheaper), fewer via LLM
- **Raise `ORCH_SUPERVISOR_MODEL`** to `claude-sonnet-4-5` → more accurate classification, higher cost

---

## MCP Platform Configuration (Phase 9)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_AUTO_DISCOVER` | `true` | Run tool discovery on startup |
| `MCP_SERVERS_DIR` | `mcp_servers` | Directory to scan for server scripts |
| `MCP_DEFAULT_TIMEOUT` | `30.0` | Per-call timeout in seconds |
| `MCP_MAX_RETRIES` | `2` | Retry count on transient failures |
| `MCP_RETRY_DELAY` | `1.0` | Delay between retries in seconds |
| `MCP_MAX_CONCURRENT` | `3` | Max concurrent tool calls |
| `MCP_NORMALIZE_ERRORS` | `true` | Wrap raw errors into standard format |
| `MCP_MIN_CONFIDENCE` | `0.60` | Minimum routing confidence to invoke MCP tools |
| `MCP_DISABLED_SERVERS` | `` | Comma-separated server names to skip (e.g. `bank-fraud-server`) |
| `MCP_PREFERRED_SERVERS` | `` | Comma-separated preferred servers for tool selection |
| `MCP_FEED_MEMORY` | `true` | Store MCP tool results in Memory Engine |
| `MCP_FEED_PROMPT` | `true` | Inject MCP results into agent system prompt |

**Examples:**
```bash
# Disable MCP fraud tools (e.g. in a read-only demo environment)
MCP_DISABLED_SERVERS=bank-fraud-server

# Tighten MCP confidence gate (only invoke for very confident queries)
MCP_MIN_CONFIDENCE=0.80

# Faster timeouts for production
MCP_DEFAULT_TIMEOUT=10.0
MCP_MAX_RETRIES=1
```

---

## Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `db/bank.db` | Path to main SQLite database |
| `SEED_DEMO_DATA` | `true` | Seed demo users/accounts on first startup |

**Demo users (seeded on `init-db`):**

| User ID | PIN | Name |
|---------|-----|------|
| `U1001` | `1111` | Alice Johnson |
| `U1002` | `2222` | Bob Smith |
| `U1003` | `3333` | Charlie Brown |

---

## API Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Bind host for uvicorn |
| `API_PORT` | `8000` | Port for FastAPI server |
| `API_WORKERS` | `1` | Number of uvicorn workers |
| `API_RELOAD` | `false` | Hot reload (dev only) |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (restrict in production) |

---

## Streamlit Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `STREAMLIT_PORT` | `8501` | Port for Streamlit server |
| `STREAMLIT_HOST` | `0.0.0.0` | Bind host |

---

## Evaluation Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EVAL_OUTPUT_PATH` | `docs/eval_results.md` | Where to write RAGAS evaluation results |
| `EVAL_DATASET_PATH` | `evaluation/dataset.json` | Path to evaluation questions |
| `RAGAS_LLM_MODEL` | `claude-sonnet-4-5` | Model for RAGAS scoring |

---

## Deployment Options

### Option 1: Local Development

```bash
pip install -r requirements.txt
cp .env.example .env
python start.py init-db
python start.py cli
```

### Option 2: Docker (Recommended for demos)

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env
docker compose up --build
```

Services started:
- `init` (one-shot): `python start.py init-db`
- `streamlit`: `http://localhost:8501`
- `api`: `http://localhost:8000`

### Option 3: Docker (Development with hot reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Mounts the project directory into containers for live code reload.

### Option 4: Production Deployment

For a production deployment, set these additional variables:

```bash
# Security
CORS_ORIGINS=https://your-domain.com

# Reliability
MCP_DEFAULT_TIMEOUT=10.0
MCP_MAX_RETRIES=1

# Performance
API_WORKERS=4

# Disable MCP debug endpoint
MCP_EXPOSE_CALL_ENDPOINT=false    # (not yet implemented — see tech debt)

# Observability
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls__your_prod_key
LANGSMITH_PROJECT=banking-assistant-prod
```

---

## Complete `.env` Template

```bash
# ── Required ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# ── LLM ─────────────────────────────────────────────────────────────────────
ANTHROPIC_MODEL=claude-sonnet-4-5
LLM_PROVIDER=anthropic

# ── LangSmith (optional) ──────────────────────────────────────────────────
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=banking-assistant
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ── Memory Engine ────────────────────────────────────────────────────────────
MEMORY_DB_PATH=db/memory.db
MEMORY_MAX_TOKENS=1200
MEMORY_MAX_FACTS=8
MEMORY_SUMMARY_THRESHOLD=10

# ── RAG ──────────────────────────────────────────────────────────────────────
CHROMA_DB_PATH=db/chroma_data
EMBEDDING_PROVIDER=sentence_transformer
VOYAGE_API_KEY=
RAG_TOP_K=3

# ── Orchestration (Phase 8) ───────────────────────────────────────────────
ORCH_HIGH_CONF=0.75
ORCH_FALLBACK_CONF=0.20
ORCH_SUPERVISOR_MODEL=claude-haiku-4-5
ORCH_ENABLE_COLLAB=true

# ── MCP Platform (Phase 9) ────────────────────────────────────────────────
MCP_AUTO_DISCOVER=true
MCP_DEFAULT_TIMEOUT=30.0
MCP_MIN_CONFIDENCE=0.60
MCP_DISABLED_SERVERS=
MCP_FEED_MEMORY=true

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH=db/bank.db
SEED_DEMO_DATA=true

# ── API Server ────────────────────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# ── Streamlit ────────────────────────────────────────────────────────────────
STREAMLIT_PORT=8501
```
