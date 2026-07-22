# MCP Servers (proof-of-concept, not wired into the core app)

This folder is a **standalone addition** demonstrating the same tool logic
exposed over the [Model Context Protocol](https://modelcontextprotocol.io)
instead of being called directly by the LangGraph agents.

**Nothing outside this folder was modified.** `agents/`, `graph.py`,
`tools/*.py`, `cli.py`, and `app_streamlit.py` are all unchanged — the core
app still calls tools directly, exactly as before. This is deliberate: MCP
adds real protocol overhead (a separate server process per tool group, a
client connection to manage) with no functional benefit at this project's
scale, since only one agent system uses these tools. It's included to
demonstrate the pattern and because MCP is widely discussed in the industry
right now, not because it solves a problem this project actually has.

## What's here

| File | What it does |
|---|---|
| `account_server.py` | MCP server exposing `get_balance`, `get_transaction_history` — thin wrapper around `tools/account_tools.py`, no reimplemented logic |
| `fraud_server.py` | MCP server exposing `lock_card`, `unlock_card`, `report_card_lost`, `report_fraud_transaction`, `get_flagged_transactions` — wraps `tools/fraud_tools.py` |
| `faq_server.py` | MCP server exposing `search_faq` — wraps `tools/faq_search.py` |
| `test_client.py` | Connects to `account_server.py`, lists its tools, calls `get_balance` and `get_transaction_history` for a real seeded user |
| `test_fraud_client.py` | Connects to `fraud_server.py`; also re-verifies the cross-user ownership check (U1003 cannot lock U1002's card) still holds through the MCP layer |
| `test_faq_client.py` | Connects to `faq_server.py`, runs a real semantic search query |

## Verified results (actually run, not assumed)

All three test clients were run against their respective servers with the
real seeded `db/bank.db`:

- `test_client.py`: correctly returned U1002's two real accounts (credit
  ₹33,674.70, checking ₹36,463.99) and 3 real transactions, entirely over
  the MCP stdio protocol.
- `test_fraud_client.py`: locked/unlocked a real card as its owner, and
  confirmed a different user (U1003) is rejected with `"Card ... not found
  for this user"` when attempting to lock it — the same ownership check
  from `tests/test_tools.py` survives being called through MCP.
- `test_faq_client.py`: correctly retrieved the "Lost or Stolen Card" FAQ
  doc as the top match for the query "what happens if I lose my card."

## Running it yourself

```bash
pip install mcp
python mcp_servers/test_client.py
python mcp_servers/test_fraud_client.py
python mcp_servers/test_faq_client.py
```

Each test client launches its server as a subprocess automatically — you
don't need to start the servers separately.

## What would be involved in actually wiring this into the agents

Right now `agents/account_agent.py` (for example) imports
`tools.account_tools.get_balance` directly. Routing it through MCP instead
would mean:

1. Adding an `agents/mcp_client.py` that manages persistent connections to
   all three servers (rather than spawning a fresh subprocess per call, as
   the test clients above do for simplicity).
2. Changing each sub-agent's tool-execution branch to call
   `mcp_client.call_tool(server, tool_name, args)` instead of importing and
   calling the Python function directly.
3. Handling connection lifecycle (start servers once at app startup, not
   per-request) and error cases specific to a subprocess-based transport
   (e.g. a crashed server process).

This is real, non-trivial surgery on working code — not done here on
purpose, so the existing verified app stays exactly as it was.
