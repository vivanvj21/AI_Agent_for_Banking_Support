// Typed API client — thin wrappers over all 15 backend endpoints.
// Each function maps 1:1 to a FastAPI route. No business logic lives here.
import api from './axios';
import type {
  LoginRequest, TokenResponse, RefreshRequest,
  ChatRequest, ChatResponse,
  VerifyRequest, VerifyResponse,
  BalanceRequest, BalanceResponse,
  HistoryRequest, HistoryResponse,
  LockCardRequest, LockCardResponse,
  ReportFraudRequest, ReportFraudResponse,
  FaqSearchRequest, FaqSearchResponse,
  HealthResponse, ReadinessResponse, MetricsResponse,
  MCPStatusResponse, MCPToolsResponse, MCPCallRequest, MCPCallResponse,
} from '@/types/api.types';

// ─── Auth ───────────────────────────────────────────────────────────────────
export const authApi = {
  login: (req: LoginRequest) =>
    api.post<TokenResponse>('/auth/login', req).then(r => r.data),
  refresh: (req: RefreshRequest) =>
    api.post<TokenResponse>('/auth/refresh', req).then(r => r.data),
};

// ─── Chat ───────────────────────────────────────────────────────────────────
export const chatApi = {
  send: (req: ChatRequest) =>
    api.post<ChatResponse>('/chat', req).then(r => r.data),
  verify: (req: VerifyRequest) =>
    api.post<VerifyResponse>('/verify', req).then(r => r.data),
};

// ─── Account ─────────────────────────────────────────────────────────────────
export const accountApi = {
  balance: (req: BalanceRequest) =>
    api.post<BalanceResponse>('/account/balance', req).then(r => r.data),
  history: (req: HistoryRequest) =>
    api.post<HistoryResponse>('/account/history', req).then(r => r.data),
};

// ─── Fraud ──────────────────────────────────────────────────────────────────
export const fraudApi = {
  lockCard: (req: LockCardRequest) =>
    api.post<LockCardResponse>('/fraud/lock-card', req).then(r => r.data),
  report: (req: ReportFraudRequest) =>
    api.post<ReportFraudResponse>('/fraud/report', req).then(r => r.data),
};

// ─── Knowledge ───────────────────────────────────────────────────────────────
export const knowledgeApi = {
  search: (req: FaqSearchRequest) =>
    api.post<FaqSearchResponse>('/faq/search', req).then(r => r.data),
};

// ─── Health ──────────────────────────────────────────────────────────────────
export const healthApi = {
  live: () => api.get<{ status: string; uptime_seconds: number }>('/health/live').then(r => r.data),
  ready: () => api.get<ReadinessResponse>('/health/ready').then(r => r.data),
  check: () => api.get<HealthResponse>('/health').then(r => r.data),
};

// ─── Metrics ─────────────────────────────────────────────────────────────────
export const metricsApi = {
  get: () => api.get<MetricsResponse>('/metrics').then(r => r.data),
};

// ─── MCP ─────────────────────────────────────────────────────────────────────
export const mcpApi = {
  status: () => api.get<MCPStatusResponse>('/mcp/status').then(r => r.data),
  tools: () => api.get<MCPToolsResponse>('/mcp/tools').then(r => r.data),
  call: (req: MCPCallRequest) =>
    api.post<MCPCallResponse>('/mcp/call', req).then(r => r.data),
};
