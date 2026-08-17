// Chat-specific types for the frontend. These extend the API types with
// additional UI state fields (isStreaming, animationStep, etc.)
export interface UIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  intent?: string;
  toolCallsLog?: UIToolCall[];
  isStreaming?: boolean; // word-reveal animation in progress
  verified?: boolean;
  turn?: number;
}

export interface UIToolCall {
  tool: string;
  agent?: string;
  status: 'pending' | 'running' | 'done';
  duration_ms?: number;
}

export interface UIConversation {
  id: string; // session_id from backend
  title: string;
  createdAt: string;
  updatedAt: string;
  pinned?: boolean;
  lastMessage?: string;
  messageCount: number;
}
