# Sequence Diagrams

> Detailed interaction sequences for the key flows in the Autonomous Banking Assistant.

---

## 1. Standard User Request (Search Intent)

```mermaid
sequenceDiagram
    actor User
    participant Interface as CLI / UI / API
    participant Graph as LangGraph (graph.py)
    participant Supervisor as supervisor_node
    participant Memory as memory_node
    participant MCP as mcp_tool_node
    participant Agent as search_agent_node
    participant LLM as Claude (Haiku/Sonnet)
    participant Tools as search_faq + ChromaDB

    User->>Interface: "What are the interest rates on savings accounts?"
    Interface->>Graph: invoke(state)

    Note over Graph,Supervisor: Stage 1: Classification
    Graph->>Supervisor: supervisor_node(state)
    Supervisor->>Supervisor: Keyword prefilter (score < 0.45, no skip)
    Supervisor->>LLM: claude-haiku classify_with_confidence()
    LLM-->>Supervisor: {intent: "search", confidence: 0.87, reasoning: "..."}
    Supervisor->>Supervisor: Composite score = 0.65×0.87 + 0.25×kw + 0.10×ctx = 0.83
    Supervisor-->>Graph: state[intent="search", routing_decision={confidence:0.83, tier:"high"}]

    Note over Graph,Memory: Stage 2: Memory Context
    Graph->>Memory: memory_node(state)
    Memory->>Memory: MemoryManager.get_context(query, session_id)
    Memory-->>Graph: state[memory_context={facts:[], summary:null}]

    Note over Graph,MCP: Stage 3: MCP Tool Pre-fetch
    Graph->>MCP: mcp_tool_node(state)
    MCP->>MCP: ToolSelector: confidence=0.83 ≥ 0.60 threshold
    MCP->>MCP: find_tools_for_intent("search") → [search_faq]
    MCP->>MCP: No user_id needed for search_faq
    MCP->>Tools: MCPClient.call("search_faq", {query: "..."})
    Tools-->>MCP: {results: [{text: "...", citation: "savings_accounts#0"}, ...]}
    MCP-->>Graph: state[mcp_context="[MCP search_faq result]\n..."]

    Note over Graph,Agent: Stage 4: Agent Execution
    Graph->>Agent: search_agent_node(state)
    Agent->>Agent: build_search_prompt(memory_context) → system_prompt
    Agent->>LLM: claude-sonnet + system_prompt + tools=[search_faq]
    LLM->>Tools: call search_faq({query: "interest rates savings"})
    Tools-->>LLM: {results: [{text, citation, distance}, ...]}
    LLM-->>Agent: "The current interest rate on savings accounts is... [savings_accounts#0]"
    Agent-->>Graph: state[reply="..."]

    Graph-->>Interface: {reply, intent, session_id, turn}
    Interface-->>User: Display response

    Note over Interface,Graph: Persist Turn
    Interface->>Graph: persist_turn(state, user_msg)
    Graph->>Graph: memory.append_message() + MemoryManager.record_turn()
```

---

## 2. Authenticated Request (Account Intent)

```mermaid
sequenceDiagram
    actor User
    participant Interface as Interface
    participant Graph as LangGraph
    participant Supervisor as Supervisor
    participant VGate as verify_gate
    participant Agent as account_agent

    User->>Interface: "Check my balance" (Payload: structured authentication fields auth_user_id="U1002", auth_pin="2222")

    Note over Graph,Supervisor: First turn — not verified
    Interface->>Graph: invoke(state[verified=false, auth_user_id="U1002", auth_pin="2222"])
    Graph->>Supervisor: classify → intent=account, confidence=0.91
    Graph->>VGate: verify_gate_node(state)
    VGate->>VGate: Read structured authentication fields auth_user_id="U1002", auth_pin="2222"
    VGate->>VGate: Clear state["auth_pin"] = None immediately after reading and before tracing/tool use
    VGate->>VGate: verify_identity("U1002", "2222") → Argon2id check → {verified: true}
    VGate-->>Graph: state[verified=true, user_id="U1002"]
    Graph->>Agent: account_agent_node(state)
    Agent->>Agent: build_account_prompt(memory_context) → system_prompt
    Agent->>Agent: run_account_agent(message, user_id=U1002, ...)
    Agent-->>Graph: state[reply="Your balance is..."]

    Note over Graph: Subsequent turns — already verified
    User->>Interface: "Show me my last 5 transactions"
    Interface->>Graph: invoke(state[verified=true, user_id=U1002])
    Graph->>Supervisor: classify → intent=account, confidence=0.95
    Graph->>Agent: Routed directly (verify_gate skipped)
    Agent-->>Graph: state[reply="Here are your recent transactions..."]
```

---

## 3. Multi-Agent Collaboration

```mermaid
sequenceDiagram
    actor User
    participant Graph as LangGraph
    participant FraudAgent as fraud_agent_node
    participant Collab as collaborator.py
    participant SearchAssist as search_faq (assist)
    participant AccountAssist as get_balance (assist)
    participant LLM as Claude Sonnet

    User->>Graph: "My card was stolen — also how does replacement work and how much do I have left?"

    Note over FraudAgent: Primary agent handles fraud action
    Graph->>FraudAgent: run_fraud_agent(message, user_id)
    FraudAgent->>LLM: call lock_card({card_id: ...})
    LLM-->>FraudAgent: "Card C3001 locked successfully."

    Note over Collab: Collaboration detection
    FraudAgent->>Collab: detect_collaboration_need(message, "fraud", trigger_keywords)
    Collab->>Collab: "also" trigger found
    Collab->>Collab: "how does replacement work" → policy signal → search needed
    Collab->>Collab: "how much do I have left" → balance signal → account needed
    Collab-->>FraudAgent: needs_collab=True, assistants=["search", "account"]

    Note over Collab: Assist 1 — Policy search
    Collab->>SearchAssist: search_faq("card replacement procedure", k=2)
    SearchAssist-->>Collab: [{text: "Replacement takes 3-5 business days...", citation: "..."}]

    Note over Collab: Assist 2 — Account balance
    Collab->>AccountAssist: get_balance(user_id=U1002)
    AccountAssist-->>Collab: {accounts: [{balance: 5000, currency: INR}]}

    Note over Collab: Merge results
    Collab->>Collab: build_collaboration_context(primary, {search: ..., account: ...})
    Collab-->>Graph: "Card C3001 locked successfully.\n\n[policy search]\nReplacement takes 3-5 days...\n\n[account info]\nCurrent balance: INR 5,000.00"
```

---

## 4. Memory Write Flow

```mermaid
sequenceDiagram
    participant Graph as graph.persist_turn()
    participant SQLMem as tools/memory.py (SQLite)
    participant MemMgr as MemoryManager
    participant MemStore as memory/store.py
    participant SemanticStore as memory/semantic_store.py (ChromaDB)
    participant Summarizer as memory/summarizer.py

    Graph->>SQLMem: append_message(session_id, turn, "user", content)
    SQLMem->>SQLMem: INSERT INTO session_messages
    Graph->>SQLMem: append_message(session_id, turn, "assistant", reply)

    Graph->>MemMgr: record_turn(session_id, user_id, "user", content)
    MemMgr->>MemStore: store_turn(session_id, user_id, "user", content)
    MemStore->>MemStore: INSERT INTO memory_turns

    MemMgr->>SemanticStore: index_turn(session_id, user_id, content)
    SemanticStore->>SemanticStore: embed(content) → ChromaDB.add()

    alt Turn count ≥ summarization threshold
        MemMgr->>Summarizer: summarize_recent_turns(session_id)
        Summarizer->>Summarizer: fetch last N turns from MemStore
        Summarizer->>Summarizer: Claude: "Summarize this conversation..."
        Summarizer-->>MemMgr: summary_text
        MemMgr->>MemStore: store_summary(session_id, summary_text)
    end
```

---

## 5. Tool Execution Flow (MCP)

```mermaid
sequenceDiagram
    participant MCPNode as mcp_tool_node
    participant Selector as ToolSelector
    participant Registry as MCPRegistry
    participant Executor as ToolExecutor
    participant Client as MCPClient
    participant Server as MCP Server (subprocess)

    MCPNode->>Selector: select_tools_for_turn(intent, message, confidence, user_id)
    Selector->>Registry: find_tools_for_intent(intent)
    Registry-->>Selector: [MCPToolEntry{name, server_name, tags}]
    Selector->>Selector: filter: needs_user_id? verified? relevant?
    Selector-->>MCPNode: ToolInvocationPlan{should_invoke=True, tool_calls=[...]}

    MCPNode->>Executor: execute_plan(plan, session_id, user_id)
    Executor->>Executor: For each tool in plan.tool_calls:
    Executor->>Registry: find_server_for_tool(tool_name)
    Registry-->>Executor: MCPServerEntry{name, script_path, status=AVAILABLE}
    Executor->>Client: MCPClient(script_path, timeout=30s).call(tool_name, args)
    Client->>Client: asyncio.run(_call_tool_async())
    Client->>Server: subprocess spawn: python mcp_servers/account_server.py
    Client->>Server: stdio: call_tool("get_balance", {user_id})
    Server-->>Client: CallToolResult{content: [{text: "{...}"}]}
    Client->>Client: parse JSON from text content
    Client-->>Executor: {accounts: [{balance: 5000, ...}]}

    Executor->>Executor: record_call(qualified_name, success=True)
    Executor->>Executor: feed_to_memory(result, session_id)
    Executor-->>MCPNode: [ToolResult{success=True, data={...}, elapsed_ms=450}]
    MCPNode->>MCPNode: format_results_for_prompt(results)
    MCPNode-->>MCPNode: state["mcp_context"] = "[MCP get_balance result]\n..."
```

---

## 6. Conversation Lifecycle

```mermaid
stateDiagram-v2
    [*] --> SessionCreated: new_session_state() or resume_session()

    SessionCreated --> Unauthenticated: Session initialized

    Unauthenticated --> Classifying: User sends message

    Classifying --> SearchRoute: intent=search, any confidence
    Classifying --> VerifyGate: intent=account or fraud, unverified
    Classifying --> Authenticated: intent=account or fraud, verified
    Classifying --> Clarify: intent=unclear or confidence < 0.20

    VerifyGate --> Authenticated: Credentials valid
    VerifyGate --> AwaitCredentials: Credentials missing or invalid
    VerifyGate --> HumanHandoff: Max retries (3) exceeded

    AwaitCredentials --> VerifyGate: User provides credentials next turn

    SearchRoute --> Responded: Search agent responds
    Authenticated --> Responded: Account/Fraud agent responds
    Clarify --> Responded: Clarification message sent

    Responded --> Classifying: User sends next message
    Responded --> SessionEnded: end_session=True (human handoff)

    HumanHandoff --> SessionEnded

    SessionEnded --> [*]
```
