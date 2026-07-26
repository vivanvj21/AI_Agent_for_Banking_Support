# API Reference

> Complete reference for all REST API endpoints exposed by the Autonomous Banking Assistant.

**Base URL (local):** `http://localhost:8000`  
**Interactive docs:** `http://localhost:8000/docs` (Swagger UI)  
**ReDoc:** `http://localhost:8000/redoc`

---

## Authentication Model

The API uses session-based identity. The flow is:

1. Call `POST /verify` with user credentials → receive `session_id`
2. Pass `session_id` in all subsequent requests
3. Protected endpoints (`/account/*`, `/fraud/*`) call `require_verified_user(session_id)` which validates the session → `user_id`

> **Security note:** The `session_id` is a server-opaque UUID. It is linked to a `user_id` in the sessions table only after successful verification. There is no JWT; the session map is stored in SQLite.

---

## Endpoints

### `POST /chat`

**Purpose:** Main conversational endpoint. Routes the user's message through the full LangGraph pipeline (supervisor → memory → MCP → agent → response).

**Request Body:**
```json
{
  "message": "What is my account balance?",
  "session_id": "optional-existing-session-uuid",
  "channel": "api"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ | User's message |
| `session_id` | string (UUID) | ❌ | Resume an existing session. If omitted, a new session is created. |
| `channel` | string | ❌ | Source channel. Default: `"api"`. Options: `"api"`, `"cli"`, `"streamlit"` |

**Response:**
```json
{
  "session_id": "uuid",
  "reply": "Your current balance is INR 5,000.00 in your savings account.",
  "intent": "account",
  "verified": true,
  "user_id": "U1002",
  "turn": 3,
  "end_session": false,
  "tool_calls_log": [
    {
      "turn": 3,
      "agent": "account_agent",
      "tool": "get_balance",
      "args": {},
      "result_summary": "{'accounts': [{'account_id': 'A1002', ..."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session UUID (persist for subsequent turns) |
| `reply` | string | Agent's response |
| `intent` | string | Classified intent: `search`, `account`, `fraud`, `unclear` |
| `verified` | boolean | Whether the user is authenticated in this session |
| `user_id` | string\|null | Authenticated user ID |
| `turn` | integer | Conversation turn number |
| `end_session` | boolean | `true` if the session has been ended (e.g. max verification retries) |
| `tool_calls_log` | array | All tool calls made during this turn |

**Status Codes:**
- `200 OK` — Success
- `503 Service Unavailable` — `ANTHROPIC_API_KEY` not configured
- `500 Internal Server Error` — Unexpected failure

**Example (curl):**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the interest rates on savings accounts?"}'
```

---

### `POST /verify`

**Purpose:** Verify a user's identity with their User ID and PIN. Links the session to the user. Required before calling `/account/*` or `/fraud/*`.

**Request Body:**
```json
{
  "user_id": "U1002",
  "pin": "2222",
  "session_id": "optional-existing-session-uuid"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | ✅ | User ID (e.g. `U1001`, `U1002`) |
| `pin` | string | ✅ | 4-digit PIN |
| `session_id` | string | ❌ | Existing session to link. If omitted, a new session is created. |

**Response (success):**
```json
{
  "verified": true,
  "user_id": "U1002",
  "first_name": "Jane",
  "session_id": "uuid",
  "error": null
}
```

**Response (failure):**
```json
{
  "verified": false,
  "user_id": null,
  "first_name": null,
  "session_id": null,
  "error": "Invalid credentials."
}
```

**Status Codes:**
- `200 OK` — Always returned (check `verified` field)
- `404 Not Found` — Unknown `session_id` provided

---

### `POST /account/balance`

**Purpose:** Retrieve account balances for the authenticated user.

**Authentication:** Required (`session_id` must be linked to a verified user)

**Request Body:**
```json
{
  "session_id": "uuid",
  "account_id": "A1002"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | ✅ | Verified session ID |
| `account_id` | string | ❌ | Specific account ID. If omitted, returns all accounts. |

**Response:**
```json
{
  "user_id": "U1002",
  "accounts": [
    {
      "account_id": "A1002",
      "account_type": "savings",
      "balance": 5000.00,
      "currency": "INR"
    }
  ]
}
```

**Status Codes:**
- `200 OK`
- `401 Unauthorized` — Session not verified

---

### `POST /account/history`

**Purpose:** Retrieve recent transactions for the authenticated user.

**Authentication:** Required

**Request Body:**
```json
{
  "session_id": "uuid",
  "account_id": "A1002",
  "limit": 10
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | ✅ | Verified session ID |
| `account_id` | string | ❌ | Filter to a specific account |
| `limit` | integer | ❌ | Max transactions to return. Default: `10` |

**Response:**
```json
{
  "user_id": "U1002",
  "transactions": [
    {
      "transaction_id": "T900001",
      "account_id": "A1002",
      "amount": -200.00,
      "description": "ATM withdrawal",
      "date": "2024-01-15",
      "type": "debit"
    }
  ]
}
```

---

### `POST /fraud/lock-card`

**Purpose:** Immediately lock a card belonging to the authenticated user. Reversible — can be unlocked later.

**Authentication:** Required

**Request Body:**
```json
{
  "session_id": "uuid",
  "card_id": "C3001"
}
```

**Response:**
```json
{
  "success": true,
  "card_id": "C3001",
  "status": "locked",
  "message": "Card C3001 has been locked."
}
```

---

### `POST /fraud/report`

**Purpose:** Flag a transaction as fraudulent for investigation.

**Authentication:** Required

**Request Body:**
```json
{
  "session_id": "uuid",
  "transaction_id": "T900001",
  "reason": "Unrecognized international charge"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | ✅ | |
| `transaction_id` | string | ✅ | Transaction to flag |
| `reason` | string | ❌ | Brief description of why it's suspicious |

**Response:**
```json
{
  "success": true,
  "transaction_id": "T900001",
  "flagged": true,
  "message": "Transaction T900001 has been flagged for investigation."
}
```

---

### `POST /faq/search`

**Purpose:** Semantic + keyword search over the FAQ/policy knowledge base. No authentication required.

**Request Body:**
```json
{
  "query": "What is the daily ATM withdrawal limit?",
  "k": 3,
  "source": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | Search query |
| `k` | integer | ❌ | Number of results. Default: `3` |
| `source` | string | ❌ | Filter by document source name |

**Response:**
```json
{
  "results": [
    {
      "text": "The daily ATM withdrawal limit is INR 20,000 for savings accounts...",
      "source": "account_types",
      "citation": "account_types#2",
      "distance": 0.18
    }
  ]
}
```

---

### `GET /health`

**Purpose:** Application-level health check. Validates startup state (directories, DB, Chroma).

**Response:**
```json
{
  "ok": true,
  "message": "Startup validation passed.",
  "details": {
    "langsmith": "disabled",
    "directories": "ok",
    "database": "ok",
    "chroma": "42 chunks indexed"
  }
}
```

---

### `GET /health/live`

**Purpose:** Kubernetes-style liveness probe. Returns `200` immediately — if the process is responding, it's alive.

**Response:** `200 OK`
```json
{"status": "ok"}
```

---

### `GET /health/ready`

**Purpose:** Kubernetes-style readiness probe. Returns `200` only after all startup initialization is complete (DB, Chroma, MCP discovery). Returns `503` if startup is still in progress.

**Response (ready):** `200 OK`
```json
{"status": "ready"}
```

**Response (not ready):** `503 Service Unavailable`
```json
{"status": "starting"}
```

---

### `GET /mcp/status`

**Purpose:** MCP Platform registry snapshot — shows all registered servers, their status, and discovered tools.

**Response:**
```json
{
  "status": "ready",
  "has_available_servers": true,
  "registry": {
    "server_count": 3,
    "available_servers": 3,
    "total_tools": 6,
    "servers": [
      {
        "name": "bank-account-server",
        "status": "available",
        "tools": [
          {"name": "get_balance", "tags": ["account", "balance"], "call_count": 0}
        ]
      }
    ]
  }
}
```

---

### `GET /mcp/tools`

**Purpose:** List all active MCP tools discovered across all available servers.

**Response:**
```json
{
  "tool_count": 6,
  "tools": [
    {
      "name": "get_balance",
      "qualified_name": "bank-account-server/get_balance",
      "server_name": "bank-account-server",
      "description": "Get balance for a specific account...",
      "tags": ["account", "balance"],
      "status": "active",
      "call_count": 12
    }
  ]
}
```

---

### `GET /mcp/tools/{intent}`

**Purpose:** List MCP tools filtered by routing intent.

**Path Parameters:**
| Parameter | Values | Description |
|-----------|--------|-------------|
| `intent` | `account`, `fraud`, `search` | Filter to tools matching this intent |

**Response:** Same structure as `GET /mcp/tools` but filtered.

---

### `POST /mcp/call`

**Purpose:** Directly invoke an MCP tool by name. Used for testing, integration, and debugging.

**Request Body:**
```json
{
  "tool_name": "get_balance",
  "tool_args": {"user_id": "U1002"},
  "server_name": "bank-account-server",
  "session_id": null,
  "user_id": null
}
```

**Response:**
```json
{
  "tool_name": "get_balance",
  "server_name": "bank-account-server",
  "success": true,
  "data": {"accounts": [...]},
  "error": "",
  "elapsed_ms": 423.5
}
```

---

### `GET /metrics`

**Purpose:** In-process request metrics for monitoring.

**Response:**
```json
{
  "request_counts": {
    "chat": 42,
    "account_balance": 18,
    "faq_search": 11
  },
  "avg_latency_ms": {
    "chat": 1240.5,
    "account_balance": 85.3,
    "faq_search": 312.1
  }
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Human-readable error message."
}
```

| Status | Meaning |
|--------|---------|
| `400 Bad Request` | Invalid request body (Pydantic validation) |
| `401 Unauthorized` | `session_id` not linked to a verified user |
| `404 Not Found` | Unknown `session_id` |
| `503 Service Unavailable` | `ANTHROPIC_API_KEY` not configured |
| `500 Internal Server Error` | Unexpected failure |

---

## Complete Example: Chat Conversation

```bash
# Step 1: Start a conversation (no auth needed for FAQ)
SESSION=$(curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the savings account interest rates?"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

echo "Session: $SESSION"

# Step 2: Verify identity
curl -s -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"U1002\", \"pin\": \"2222\", \"session_id\": \"$SESSION\"}" \
  | python -m json.tool

# Step 3: Check balance (session now verified)
curl -s -X POST http://localhost:8000/account/balance \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION\"}" \
  | python -m json.tool

# Step 4: Lock a card
curl -s -X POST http://localhost:8000/fraud/lock-card \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION\", \"card_id\": \"C3001\"}" \
  | python -m json.tool
```
