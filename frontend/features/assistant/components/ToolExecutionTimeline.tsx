// ToolExecutionTimeline — animated step-by-step replay of agent execution.
// This is the key "AI-first" differentiator. Instead of showing "Thinking...",
// we show exactly which agents ran and what tools they called.
// The animation replays tool_calls_log from the API response.
'use client';
import { motion } from 'framer-motion';
import { Check, Loader2, Brain, Building2, Shield, BookOpen, Zap } from 'lucide-react';
import type { UIToolCall } from '../types/chat.types';

const TOOL_ICONS: Record<string, React.ElementType> = {
  supervisor: Brain,
  account: Building2,
  fraud: Shield,
  search: BookOpen,
  faq: BookOpen,
  default: Zap,
};

const TOOL_COLORS: Record<string, string> = {
  supervisor: 'text-violet-400',
  account: 'text-cyan-400',
  fraud: 'text-red-400',
  search: 'text-green-400',
  faq: 'text-green-400',
  default: 'text-white/40',
};

function getToolKey(name: string): string {
  const n = name.toLowerCase();
  for (const key of Object.keys(TOOL_ICONS)) {
    if (n.includes(key)) return key;
  }
  return 'default';
}

function formatToolName(tool: string): string {
  return tool
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace('Get ', '')
    .replace('Fetch ', '');
}

interface ToolExecutionTimelineProps {
  toolCalls: UIToolCall[];
  isStreaming: boolean; // shows spinner on last item if still loading
}

export function ToolExecutionTimeline({ toolCalls, isStreaming }: ToolExecutionTimelineProps) {
  if (!toolCalls.length && !isStreaming) return null;

  return (
    <div className="mb-3 space-y-1">
      {toolCalls.map((call, i) => {
        const key = getToolKey(call.agent ?? call.tool);
        const Icon = TOOL_ICONS[key];
        const color = TOOL_COLORS[key];
        const isLast = i === toolCalls.length - 1;
        const showSpinner = isLast && isStreaming;

        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.15, duration: 0.3 }}
            className="flex items-center gap-2 text-xs"
          >
            {/* Status icon */}
            <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
              {showSpinner ? (
                <Loader2 className="w-3 h-3 text-violet-400 animate-spin" />
              ) : (
                <Check className="w-3 h-3 text-green-400" />
              )}
            </div>

            {/* Agent icon */}
            <Icon className={`w-3 h-3 ${color} flex-shrink-0`} />

            {/* Tool name */}
            <span className="text-white/50">
              {formatToolName(call.tool)}
              {call.agent && call.agent !== call.tool && (
                <span className="text-white/25 ml-1">via {call.agent}</span>
              )}
            </span>

            {/* Duration */}
            {call.duration_ms && (
              <span className="text-white/20 font-mono ml-auto">{call.duration_ms.toFixed(0)}ms</span>
            )}
          </motion.div>
        );
      })}

      {/* Thinking placeholder when no tool calls yet */}
      {!toolCalls.length && isStreaming && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center gap-2 text-xs text-white/30"
        >
          <Loader2 className="w-3 h-3 animate-spin text-violet-400" />
          <Brain className="w-3 h-3 text-violet-400" />
          <span>Supervisor routing request…</span>
        </motion.div>
      )}
    </div>
  );
}
