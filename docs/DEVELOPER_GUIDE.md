# Developer Guide

> How to extend, customize, and contribute to the Autonomous Banking Assistant.

---

## Table of Contents

1. [Project Setup](#project-setup)
2. [How to Add a New Agent](#how-to-add-a-new-agent)
3. [How to Add a New MCP Server](#how-to-add-a-new-mcp-server)
4. [How to Add New Tools](#how-to-add-new-tools)
5. [How to Extend Memory](#how-to-extend-memory)
6. [How to Change the LLM Provider](#how-to-change-the-llm-provider)
7. [How to Extend the Routing Configuration](#how-to-extend-the-routing-configuration)
8. [How to Add a New API Endpoint](#how-to-add-a-new-api-endpoint)
9. [Running the Evaluation Harness](#running-the-evaluation-harness)
10. [LangSmith Tracing Setup](#langsmith-tracing-setup)

---

## Project Setup

### Prerequisites

- Python 3.12+
- Docker + Docker Compose (for containerized deployment)
- `ANTHROPIC_API_KEY` from [console.anthropic.com](https://console.anthropic.com)

### Local Development

```bash
# Clone
git clone <repo-url>
cd "AI Agent for Banking Support"

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env → set ANTHROPIC_API_KEY at minimum

# Initialize database + Chroma index
python start.py init-db

# Validate setup
python start.py check

# Run
python start.py cli           # terminal
python start.py streamlit     # browser UI at http://localhost:8501
python start.py api           # REST API at http://localhost:8000
```

### Project Layout Quick Reference

```
agents/                # Supervisor, registry, confidence, agents, prompt_builder
├── supervisor.py      # 3-stage classification pipeline
├── registry.py        # AgentCapability descriptors
├── confidence.py      # Routing score computation
├── prompt_builder.py  # Centralized prompt construction
├── orchestration_config.py  # Env-driven routing config
├── collaborator.py    # Multi-agent assist
├── state.py           # AgentState TypedDict
├── account_agent.py
├── fraud_agent.py
├── search_agent.py
└── verification.py    # Hard Python identity check

graph.py               # LangGraph StateGraph — main orchestration entry point

mcp_platform/          # MCP Manager, Registry, Client, Executor, Selector
mcp_servers/           # FastMCP server definitions

memory/                # Memory Engine (SQLite + ChromaDB)
tools/                 # Business logic functions called by agents

api/                   # FastAPI application
├── main.py            # App factory, lifespan
├── routes.py          # Core endpoints
├── mcp_routes.py      # /mcp/* endpoints
├── schemas.py         # Pydantic request/response models
├── health.py          # /health/live, /health/ready
└── dependencies.py    # get_graph(), require_verified_user()

db/                    # SQLite schema + seeding
knowledge_base/        # FAQ/policy Markdown docs for RAG
evaluation/            # RAGAS evaluation harness
observability/         # LangSmith tracing helpers
```

---

## How to Add a New Agent

Adding a new agent (e.g. a `LoanAgent` for loan inquiries) requires 4 steps.

### Step 1: Create the agent module

```python
# agents/loan_agent.py
from anthropic import Anthropic
from config import require_llm_config

_anthropic_client = None

def get_client():
    global _anthropic_client
    if _anthropic_client is None:
        config = require_llm_config()
        _anthropic_client = Anthropic(api_key=config.api_key)
    return _anthropic_client

TOOLS = [
    {
        "name": "get_loan_status",
        "description": "Check the status of the user's loan application.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "loan_id": {"type": "string"},
            },
            "required": ["user_id"],
        },
    }
]

SYSTEM_PROMPT = """You are the Loan Agent for a bank's support system.
The user is already identity-verified.
Help them with loan inquiries using your tools."""

def run_loan_agent(
    user_message: str,
    user_id: str,
    tool_log: list,
    turn: int,
    max_tool_iters: int = 3,
    system_prompt_override: str | None = None,
) -> str:
    effective_prompt = system_prompt_override or SYSTEM_PROMPT
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_tool_iters):
        response = get_client().messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=effective_prompt,
            tools=TOOLS,
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            return "\n".join(b.text for b in response.content if b.type == "text").strip()
        # ... tool handling loop (same pattern as fraud_agent.py)
    return "Unable to process that request."
```

### Step 2: Register the agent capability

```python
# agents/registry.py — add this entry:
LOAN_AGENT = AgentCapability(
    name="loan",
    display_name="Loan Agent",
    description="Handles loan status inquiries and loan-related questions.",
    supported_intents=["loan"],
    supported_tools=["get_loan_status"],
    requires_verification=True,
    priority=2,
    base_confidence=0.85,
    keywords=["loan", "emi", "mortgage", "repayment", "interest", "outstanding"],
    examples=[
        "What is my loan status?",
        "How much EMI do I have left?",
    ],
)

# Add to AGENT_REGISTRY:
AGENT_REGISTRY: list[AgentCapability] = sorted(
    [SEARCH_AGENT, ACCOUNT_AGENT, FRAUD_AGENT, LOAN_AGENT],
    key=lambda a: a.priority,
)
```

### Step 3: Add the graph node

```python
# graph.py

# Import
from agents.loan_agent import run_loan_agent

# Add node function
def loan_agent_node(state: AgentState) -> AgentState:
    with trace_node("loan_agent", ...):
        last_user_msg = state["messages"][-1]["content"]
        system_prompt = build_loan_prompt(memory_context=state.get("memory_context"))
        reply = run_loan_agent(
            last_user_msg, state["user_id"], state["tool_calls_log"], state["turn"],
            system_prompt_override=system_prompt,
        )
        state["reply"] = reply
    return state

# In build_graph():
graph.add_node("loan_agent", loan_agent_node)

# In route_after_supervisor():
if intent == "loan":
    if state.get("verified"):
        return "loan_agent"
    return "verify_gate"

# Add edge
graph.add_edge("loan_agent", END)
```

### Step 4: Add a prompt builder

```python
# agents/prompt_builder.py — add:
_LOAN_BASE = """You are the Loan Agent for a bank's support system.
The user is authenticated. Help them with loan status, EMI, repayment queries."""

def build_loan_prompt(memory_context: dict | None = None, max_tokens: int = 1000) -> str:
    parts = [_LOAN_BASE]
    _inject_memory(parts, memory_context, max_tokens - _estimate_tokens(_LOAN_BASE))
    return "\n\n".join(parts)
```

That's it. The supervisor will automatically classify "loan" intent and route to your new agent.

---

## How to Add a New MCP Server

### Step 1: Create the FastMCP server script

```python
# mcp_servers/loan_server.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from mcp_servers.common import safe_mcp_call

mcp = FastMCP("bank-loan-server")

@mcp.tool()
def get_loan_status(user_id: str, loan_id: str | None = None) -> dict:
    """Get the status of loans for a user."""
    from tools.loan_tools import get_loan_status as _get_loan_status  # your new tool
    return safe_mcp_call("get_loan_status", _get_loan_status, user_id=user_id, loan_id=loan_id)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Step 2: Register it in MCP Platform config

```python
# mcp_platform/config.py — in the servers list:
MCPServerConfig(
    name="bank-loan-server",
    script_path="mcp_servers/loan_server.py",
    description="Loan status and repayment tools",
    tags=["loan", "emi", "repayment"],
),
```

### Step 3: Add intent tag mapping

```python
# mcp_platform/discovery.py — in _SERVER_INTENT_MAP:
_SERVER_INTENT_MAP: dict[str, list[str]] = {
    ...
    "bank-loan-server": ["loan", "emi", "repayment"],
}
```

The MCP Manager will auto-discover your tool at startup via `list_tools()`. No further changes needed.

---

## How to Add New Tools

Tools are plain Python functions in `tools/`. They must:
- Accept `user_id` as a required parameter for user-scoped operations
- Return a `dict` (not raise exceptions for business errors)
- Have no side effects on global state

```python
# tools/loan_tools.py
import sqlite3
from db.connection import get_db_path

def get_loan_status(user_id: str, loan_id: str | None = None) -> dict:
    """Return loan status for a user."""
    conn = sqlite3.connect(get_db_path())
    # ... query loans table
    conn.close()
    return {"user_id": user_id, "loans": [...]}
```

Then expose the tool to an agent:
1. Add it to the agent's `TOOLS` list (Anthropic tool format)
2. Add it to the agent's `fn_map` in the tool execution loop
3. Optionally expose it via an MCP server (see above)

---

## How to Extend Memory

The Memory Engine has 4 extension points:

### 1. Custom Fact Extractors

```python
# memory/extractor.py (create this)
def extract_facts_from_turn(role: str, content: str) -> list[str]:
    """Extract long-term facts from a conversation turn."""
    facts = []
    if "prefer" in content.lower():
        facts.append(f"User preference: {content[:100]}")
    return facts
```

Then call from `MemoryManager.record_turn()`.

### 2. Custom Rankers

```python
# memory/ranking.py — add a new scoring function:
def custom_score(fact: str, query: str, age_hours: float) -> float:
    base = recency_score(age_hours) + relevance_score(fact, query)
    # Add domain-specific boost
    if "fraud" in fact.lower() and "fraud" in query.lower():
        base += 0.2
    return min(1.0, base)
```

### 3. Increase Context Budget

```bash
# .env
MEMORY_MAX_TOKENS=2000          # default: 1200
MEMORY_MAX_FACTS=12             # default: 8
```

### 4. Custom Summarization Prompt

Edit `memory/summarizer.py` → `SUMMARIZATION_PROMPT`. The default produces bullet-point summaries; you can change it to produce structured YAML, JSON, etc.

---

## How to Change the LLM Provider

The `config.py` module has a `LLM_PROVIDER` env variable.

Currently, only `anthropic` is supported. To add a new provider:

### Step 1: Extend `get_llm_config()`

```python
# config.py
def get_llm_config(provider: str | None = None) -> LLMProviderConfig:
    selected = (provider or os.environ.get("LLM_PROVIDER") or "anthropic").lower()
    if selected == "openai":
        return LLMProviderConfig(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        )
    elif selected == "anthropic":
        ...
```

### Step 2: Update agent clients

Each agent (`account_agent.py`, `fraud_agent.py`, etc.) initializes `Anthropic()` directly. Refactor to use a factory:

```python
# config.py — add:
def get_llm_client():
    cfg = require_llm_config()
    if cfg.provider == "anthropic":
        from anthropic import Anthropic
        return Anthropic(api_key=cfg.api_key), cfg.model
    elif cfg.provider == "openai":
        from openai import OpenAI
        return OpenAI(api_key=cfg.api_key), cfg.model
```

Then update `get_client()` in each agent to call `get_llm_client()`.

---

## How to Extend the Routing Configuration

All routing thresholds are env-driven via `agents/orchestration_config.py`:

```bash
# Confidence thresholds
ORCH_HIGH_CONF=0.75          # Direct routing
ORCH_MED_CONF=0.50           # Route with fallback flag
ORCH_LOW_CONF=0.30           # Try, be ready to escalate
ORCH_FALLBACK_CONF=0.20      # Below this → clarify

# Supervisor model
ORCH_SUPERVISOR_MODEL=claude-haiku-4-5

# Context limits
ORCH_MAX_CTX_TOKENS=3000
ORCH_MAX_HISTORY_TURNS=10

# Collaboration
ORCH_ENABLE_COLLAB=true
```

To add a new fallback rule:

```python
# agents/orchestration_config.py — in fallback_rules:
fallback_rules: dict[str, str] = field(default_factory=lambda: {
    "account": "search",
    "fraud": "search",
    "loan": "search",      # new
    "search": "clarify",
    "unclear": "clarify",
})
```

---

## How to Add a New API Endpoint

```python
# api/routes.py — add your endpoint:
from api.schemas import MyRequest, MyResponse

@router.post("/my-endpoint", response_model=MyResponse)
def my_endpoint(payload: MyRequest) -> MyResponse:
    name, start = _timed("my_endpoint")
    try:
        # call existing tools / graph functions
        result = some_tool_function(...)
        return MyResponse(**result)
    finally:
        record_request(name, time.perf_counter() - start)
```

```python
# api/schemas.py — add your schemas:
class MyRequest(BaseModel):
    session_id: str
    my_field: str

class MyResponse(BaseModel):
    result: str
    success: bool
```

No changes needed to `main.py` — all routes in `router` are automatically registered.

---

## Running the Evaluation Harness

```bash
# Run RAGAS evaluation (requires ANTHROPIC_API_KEY)
cd evaluation/
python run_eval.py

# View results
cat ../docs/eval_results.md
```

The evaluation harness:
1. Runs a test suite of golden question/answer pairs
2. Calls the graph for each question
3. Scores responses with RAGAS metrics (faithfulness, answer relevancy, context precision)
4. Writes results to `docs/eval_results.md`

To add new evaluation cases:
```python
# evaluation/test_cases.py
TEST_CASES = [
    {
        "question": "What is the card replacement procedure?",
        "expected_answer_contains": ["3-5 business days", "replacement"],
        "intent": "search",
    },
    # ... add more
]
```

---

## LangSmith Tracing Setup

```bash
# .env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=banking-assistant
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

Once enabled, every graph invocation produces a trace in your LangSmith project showing:
- All node executions and timing
- LLM inputs/outputs and token counts
- Tool call arguments and results
- Session and turn metadata

Traces are tagged with `node:supervisor`, `node:search_agent`, etc. for easy filtering.
