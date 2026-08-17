// useChat — manages the full chat session lifecycle.
// Key design decisions:
// 1. Messages stored in React state (not TanStack Query) — they are local UI state, not server cache.
// 2. Word-reveal animation: we receive the full response and animate it character-by-character
//    client-side (backend doesn't stream). This creates the "AI typing" feel.
// 3. session_id is persisted in state and reused across turns for conversation continuity.
'use client';
import { useState, useCallback, useRef } from 'react';
import { chatApi } from '@/lib/api';
import type { UIMessage, UIToolCall } from '../types/chat.types';
import type { ToolCallLog } from '@/types/api.types';

function mapToolCalls(logs: ToolCallLog[]): UIToolCall[] {
  return logs.map(l => ({
    tool: l.tool,
    agent: l.agent,
    status: 'done' as const,
    duration_ms: l.duration_ms,
  }));
}

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

export function useChat(initialSessionId?: string) {
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>(initialSessionId);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);

  // Animate text word-by-word to simulate streaming
  const animateText = useCallback((messageId: string, fullText: string) => {
    const words = fullText.split(' ');
    let built = '';
    let i = 0;

    const step = () => {
      if (abortRef.current) return;
      if (i >= words.length) {
        // Animation complete — mark as no longer streaming
        setMessages(prev => prev.map(m =>
          m.id === messageId ? { ...m, isStreaming: false } : m,
        ));
        return;
      }
      built += (i > 0 ? ' ' : '') + words[i];
      setMessages(prev => prev.map(m =>
        m.id === messageId ? { ...m, content: built } : m,
      ));
      i++;
      // Speed: ~40ms per word for comfortable reading pace
      setTimeout(step, 40);
    };
    step();
  }, []);

  const sendMessage = useCallback(async (text: string, authUserId?: string, authPin?: string) => {
    if (!text.trim() || isLoading) return;

    abortRef.current = false;
    setError(null);
    setIsLoading(true);

    // Add user message immediately (optimistic)
    const userMsg: UIMessage = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);

    // Add placeholder assistant message with streaming=true for thinking indicator
    const assistantId = generateId();
    const placeholderMsg: UIMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, placeholderMsg]);

    try {
      const res = await chatApi.send({
        message: text.trim(),
        session_id: sessionId,
        channel: 'web',
        auth: authUserId && authPin ? { user_id: authUserId, pin: authPin } : undefined,
      });

      // Persist session_id for conversation continuity
      if (!sessionId && res.session_id) setSessionId(res.session_id);

      // Update placeholder with tool calls, then animate text
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? {
          ...m,
          intent: res.intent,
          toolCallsLog: mapToolCalls(res.tool_calls_log),
          verified: res.verified,
          turn: res.turn,
          isStreaming: true, // still streaming (text animation)
        } : m,
      ));

      // Start word-reveal animation with the full response
      animateText(assistantId, res.reply);

    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Something went wrong. Please try again.';
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: msg, isStreaming: false } : m,
      ));
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, sessionId, animateText]);

  const clearMessages = useCallback(() => {
    abortRef.current = true;
    setMessages([]);
    setSessionId(undefined);
    setError(null);
  }, []);

  return { messages, sessionId, isLoading, error, sendMessage, clearMessages };
}
