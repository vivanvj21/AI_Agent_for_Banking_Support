// ChatInput — message composer at the bottom of the chat window.
// Auto-expands for long messages, sends on Enter (Shift+Enter for newline).
'use client';
import { useRef, useEffect, KeyboardEvent } from 'react';
import { ArrowUp, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatInputProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ value, onChange, onSend, isLoading, disabled, placeholder }: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea as content grows
  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = 'auto';
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 160)}px`;
    }
  }, [value]);

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim()) onSend();
    }
  };

  const canSend = value.trim().length > 0 && !isLoading && !disabled;

  return (
    <div className="relative flex items-end gap-3 p-3 rounded-2xl border border-white/8 bg-[hsl(222,37%,10%)] focus-within:border-violet-500/40 transition-colors">
      <textarea
        ref={ref}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKey}
        placeholder={placeholder ?? 'Ask about your account, cards, or banking policies…'}
        disabled={disabled}
        rows={1}
        className={cn(
          'flex-1 bg-transparent text-sm text-white placeholder:text-white/20 resize-none outline-none',
          'leading-relaxed py-1.5 scrollbar-hide',
        )}
        style={{ minHeight: '24px', maxHeight: '160px' }}
      />
      <button
        onClick={onSend}
        disabled={!canSend}
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all',
          canSend
            ? 'bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/20'
            : 'bg-white/5 text-white/20 cursor-not-allowed',
        )}
      >
        {isLoading
          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
          : <ArrowUp className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}
