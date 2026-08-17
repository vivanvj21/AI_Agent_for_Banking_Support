// TanStack Query key factory — centralises all cache keys.
// Using factory functions (not string literals) ensures cache keys are
// consistent across the app and makes invalidation explicit and refactor-safe.
export const queryKeys = {
  // Auth
  user: () => ['user'] as const,

  // Account — session_id scoped to avoid cross-user cache leaks
  balance: (sessionId: string) => ['balance', sessionId] as const,
  transactions: (sessionId: string, limit?: number) => ['transactions', sessionId, limit] as const,

  // Knowledge
  faqSearch: (query: string, k?: number) => ['faq', query, k] as const,

  // Infra
  health: () => ['health'] as const,
  readiness: () => ['readiness'] as const,
  metrics: () => ['metrics'] as const,

  // MCP
  mcpStatus: () => ['mcp', 'status'] as const,
  mcpTools: () => ['mcp', 'tools'] as const,
  mcpToolsForIntent: (intent: string) => ['mcp', 'tools', intent] as const,
} as const;
