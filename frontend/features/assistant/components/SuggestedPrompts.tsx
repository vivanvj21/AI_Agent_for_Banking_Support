// SuggestedPrompts — chip grid shown on empty state.
// Helps new users understand what the AI can do.
// Each chip is a one-click starter for a common banking query.
import { motion } from 'framer-motion';
import { TrendingUp, CreditCard, HelpCircle, Lock, AlertTriangle, Brain } from 'lucide-react';

const PROMPTS = [
  { icon: TrendingUp, text: 'Show my last 5 transactions', color: 'text-cyan-400' },
  { icon: CreditCard, text: 'What is my current balance?', color: 'text-violet-400' },
  { icon: Lock, text: 'Lock my card immediately', color: 'text-red-400' },
  { icon: HelpCircle, text: 'What is UPI Lite?', color: 'text-green-400' },
  { icon: AlertTriangle, text: 'Report a suspicious transaction', color: 'text-yellow-400' },
  { icon: Brain, text: 'Explain my spending pattern', color: 'text-pink-400' },
];

interface SuggestedPromptsProps {
  onSelect: (prompt: string) => void;
}

export function SuggestedPrompts({ onSelect }: SuggestedPromptsProps) {
  return (
    <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
      {PROMPTS.map((p, i) => (
        <motion.button
          key={p.text}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 + i * 0.08, duration: 0.3 }}
          onClick={() => onSelect(p.text)}
          className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-white/6 bg-white/2 hover:bg-white/5 hover:border-white/10 transition-all text-left group"
        >
          <p.icon className={`w-3.5 h-3.5 ${p.color} flex-shrink-0`} />
          <span className="text-xs text-white/50 group-hover:text-white/70 transition-colors leading-snug">{p.text}</span>
        </motion.button>
      ))}
    </div>
  );
}
