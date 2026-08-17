// TypeScript mirrors of all backend Pydantic schemas.
// These are the single source of truth for all API request/response shapes.
// When the backend schema changes, update this file first.

// ─── Auth ───────────────────────────────────────────────────────────────────

export interface LoginRequest {
  user_id: string;
  pin: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  user_id: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

// ─── Chat ───────────────────────────────────────────────────────────────────

export interface AuthInput {
  user_id: string;
  pin: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  channel?: string;
  auth?: AuthInput;
}

export interface ToolCallLog {
  tool: string;
  agent?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  duration_ms?: number;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  intent?: string;
  verified: boolean;
  user_id?: string;
  turn: number;
  end_session: boolean;
  tool_calls_log: ToolCallLog[];
}

// ─── Verify ─────────────────────────────────────────────────────────────────

export interface VerifyRequest {
  user_id: string;
  pin: string;
  session_id?: string;
}

export interface VerifyResponse {
  verified: boolean;
  user_id?: string;
  first_name?: string;
  session_id?: string;
  error?: string;
}

// ─── Account ─────────────────────────────────────────────────────────────────

export interface BalanceRequest {
  session_id: string;
  account_id?: string;
}

export interface AccountData {
  account_id: string;
  account_type: string;
  balance_paise: number;
  balance: number;
  balance_formatted: string;
  currency: string;
}

export interface BalanceResponse {
  accounts?: AccountData[];
  account_id?: string;
  account_type?: string;
  balance_paise?: number;
  balance?: number;
  balance_formatted?: string;
  currency?: string;
  error?: string;
}

export interface HistoryRequest {
  session_id: string;
  account_id?: string;
  limit?: number;
}

export interface Transaction {
  transaction_id: string;
  account_id: string;
  amount: number;
  amount_paise: number;
  description: string;
  type: 'credit' | 'debit';
  date: string;
  merchant?: string;
  category?: string;
  flagged_fraud?: boolean;
}

export interface HistoryResponse {
  transactions: Transaction[];
  error?: string;
}

// ─── Fraud ──────────────────────────────────────────────────────────────────

export interface LockCardRequest {
  session_id: string;
  card_id: string;
}

export interface LockCardResponse {
  status?: string;
  card_id?: string;
  error?: string;
}

export interface ReportFraudRequest {
  session_id: string;
  transaction_id: string;
  reason?: string;
}

export interface ReportFraudResponse {
  status?: string;
  transaction_id?: string;
  reported_at?: string;
  note?: string;
  error?: string;
}

// ─── FAQ Search ──────────────────────────────────────────────────────────────

export interface FaqSearchRequest {
  query: string;
  k?: number;
  source?: string;
}

export interface FaqResult {
  text: string;
  source?: string;
  score?: number;
  metadata?: Record<string, unknown>;
}

export interface FaqSearchResponse {
  results: FaqResult[];
  warning?: string;
}

// ─── Health ──────────────────────────────────────────────────────────────────

export interface HealthResponse {
  ok: boolean;
  message: string;
  details: Record<string, string>;
}

export interface ReadinessResponse {
  status: string;
  ready: boolean;
  uptime_seconds: number;
  checks: {
    database: 'ok' | 'failed';
    vector_store: 'ok' | 'failed';
    mcp_platform: 'ok' | 'failed';
    configuration: 'ok' | 'failed';
  };
}

// ─── Metrics ─────────────────────────────────────────────────────────────────

export interface MetricsResponse {
  uptime_seconds: number;
  request_counts: Record<string, number>;
  average_latency_ms: Record<string, number>;
}

// ─── MCP ─────────────────────────────────────────────────────────────────────

export interface MCPTool {
  name: string;
  description: string;
  server: string;
  status: string;
}

export interface MCPStatusResponse {
  status: string;
  has_available_servers: boolean;
  registry: Record<string, unknown>;
}

export interface MCPToolsResponse {
  tool_count: number;
  tools: MCPTool[];
}

export interface MCPCallRequest {
  tool_name: string;
  tool_args?: Record<string, unknown>;
  server_name?: string;
  session_id?: string;
  user_id?: string;
}

export interface MCPCallResponse {
  tool_name: string;
  server_name: string;
  success: boolean;
  data: Record<string, unknown>;
  error: string;
  elapsed_ms: number;
}

// ─── Frontend-only types ─────────────────────────────────────────────────────

// A chat message as stored in frontend state (richer than the API shape)
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  intent?: string;
  tool_calls_log?: ToolCallLog[];
  verified?: boolean;
  isStreaming?: boolean; // client-side word-reveal state
}

// A conversation (session) record stored in localStorage for the sidebar
export interface Conversation {
  id: string; // session_id
  title: string;
  createdAt: string;
  updatedAt: string;
  pinned?: boolean;
  messageCount: number;
  lastMessage?: string;
}

// Typed API error for display in the UI
export interface APIError {
  message: string;
  status: number;
  endpoint: string;
}
