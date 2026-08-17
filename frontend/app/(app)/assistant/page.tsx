// AI Assistant page — THE CENTERPIECE of the platform.
// Layout: ChatGPT-style with conversation sidebar (desktop) + main chat area.
// After login, this is the DEFAULT route users land on.
'use client';
import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Zap, MessageSquare, Trash2 } from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { useChat } from '@/features/assistant/hooks/useChat';
import { AssistantMessage } from '@/features/assistant/components/AssistantMessage';
import { ChatInput } from '@/features/assistant/components/ChatInput';
import { SuggestedPrompts } from '@/features/assistant/components/SuggestedPrompts';
import { cn } from '@/lib/utils';

export default function AssistantPage() {
  const { user } = useAuth();
  const [input, setInput] = useState('');
  const { messages, isLoading, sendMessage, clearMessages } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim());
    setInput('');
  };

  const handleSuggest = (prompt: string) => {
    sendMessage(prompt);
  };

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 18) return 'Good afternoon';
    return 'Good evening';
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* Conversation sidebar — desktop only */}
      <aside className="hidden xl:flex flex-col w-64 border-r border-white/5 bg-[hsl(222,42%,7%)] flex-shrink-0">
        <div className="p-3 border-b border-white/5">
          <button
            onClick={clearMessages}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-white/50 border border-white/8 hover:bg-white/5 hover:text-white/80 transition-all"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>
        <div className="flex-1 p-3">
          <p className="text-[10px] uppercase tracking-widest text-white/20 px-2 mb-2">Recent</p>
          {messages.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 text-sm text-white/70">
              <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-violet-400" />
              <span className="truncate text-xs">{messages[0]?.content?.slice(0, 40) ?? 'New conversation'}</span>
            </div>
          )}
          {messages.length === 0 && (
            <p className="text-xs text-white/15 px-2">No conversations yet</p>
          )}
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Messages area */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-4 py-6 scrollbar-hide"
        >
          {/* Empty state */}
          <AnimatePresence>
            {isEmpty && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center h-full gap-8 min-h-[60vh]"
              >
                {/* Greeting */}
                <div className="text-center">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center mx-auto mb-5 shadow-xl shadow-violet-500/25">
                    <Zap className="w-7 h-7 text-white" />
                  </div>
                  <h2 className="text-2xl font-semibold text-white mb-2">
                    {greeting()}, {user?.firstName ?? user?.userId} 👋
                  </h2>
                  <p className="text-white/40 text-sm">
                    Ask anything about your banking
                  </p>
                </div>

                {/* Suggested prompts */}
                <SuggestedPrompts onSelect={handleSuggest} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Message list */}
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map(msg => (
              <div key={msg.id}>
                {msg.role === 'user' ? (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-end"
                  >
                    <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-br-md bg-violet-600 text-white text-sm leading-relaxed">
                      {msg.content}
                    </div>
                  </motion.div>
                ) : (
                  <AssistantMessage message={msg} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Input area */}
        <div className="flex-shrink-0 px-4 pb-4">
          <div className="max-w-3xl mx-auto">
            {messages.length > 0 && (
              <div className="flex justify-end mb-2">
                <button
                  onClick={clearMessages}
                  className="flex items-center gap-1 text-xs text-white/20 hover:text-white/50 transition-colors"
                >
                  <Trash2 className="w-3 h-3" /> Clear chat
                </button>
              </div>
            )}
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={handleSend}
              isLoading={isLoading}
            />
            <p className="text-center text-[10px] text-white/15 mt-2">
              AI may make mistakes. Verify important financial information.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
