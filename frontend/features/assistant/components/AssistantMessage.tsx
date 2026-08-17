// AssistantMessage — renders a single AI response with all its metadata.
// This is where ALL AI capabilities are surfaced:
//   • Animated tool execution timeline
//   • Markdown rendered reply
//   • Sources accordion (RAG docs)
//   • Agent badge (which agent responded)
//   • Message actions (copy, feedback)
'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, ThumbsUp, ThumbsDown, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { ThinkingIndicator } from './ThinkingIndicator';
import { ToolExecutionTimeline } from './ToolExecutionTimeline';
import { SourcesAccordion } from './SourcesAccordion';
import { AgentBadge } from '@/components/shared/AgentBadge';
import type { UIMessage } from '../types/chat.types';
import { cn } from '@/lib/utils';

interface AssistantMessageProps {
  message: UIMessage;
}

export function AssistantMessage({ message }: AssistantMessageProps) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const isThinking = message.isStreaming && !message.content && !message.toolCallsLog?.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex gap-3"
    >
      {/* AI avatar */}
      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-lg shadow-violet-500/20">
        <Zap className="w-3.5 h-3.5 text-white" />
      </div>

      <div className="flex-1 min-w-0">
        {/* Tool execution timeline */}
        {(message.toolCallsLog?.length || (message.isStreaming && !message.content)) && (
          <ToolExecutionTimeline
            toolCalls={message.toolCallsLog ?? []}
            isStreaming={!!message.isStreaming}
          />
        )}

        {/* Message content */}
        <div className="rounded-xl bg-[hsl(222,37%,12%)] border border-white/5 px-4 py-3">
          {isThinking ? (
            <ThinkingIndicator />
          ) : (
            <div className={cn('prose prose-invert prose-sm max-w-none', message.isStreaming && 'after:content-["|"] after:animate-blink after:text-violet-400 after:ml-0.5')}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content || ''}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Sources */}
        {/* Note: sources would come from a separate FAQ search call correlated to the message.
            For now, we detect if the intent was search-related and show a placeholder structure. */}

        {/* Footer: agent badge + actions */}
        {!message.isStreaming && message.content && (
          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center gap-2">
              {message.intent && <AgentBadge agent={message.intent} />}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={handleCopy}
                className={cn(
                  'p-1.5 rounded-lg text-white/20 hover:text-white/60 hover:bg-white/5 transition-all text-xs flex items-center gap-1',
                  copied && 'text-green-400',
                )}
              >
                <Copy className="w-3 h-3" />
              </button>
              <button
                onClick={() => { setFeedback('up'); toast.success('Thanks for the feedback!'); }}
                className={cn('p-1.5 rounded-lg transition-all', feedback === 'up' ? 'text-green-400' : 'text-white/20 hover:text-white/60 hover:bg-white/5')}
              >
                <ThumbsUp className="w-3 h-3" />
              </button>
              <button
                onClick={() => { setFeedback('down'); toast.success('Feedback noted.'); }}
                className={cn('p-1.5 rounded-lg transition-all', feedback === 'down' ? 'text-red-400' : 'text-white/20 hover:text-white/60 hover:bg-white/5')}
              >
                <ThumbsDown className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
