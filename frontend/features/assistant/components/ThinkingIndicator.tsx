// ThinkingIndicator — animated dots shown while waiting for AI response.
// Three dots animate in sequence to indicate "the AI is thinking".
'use client';
import { motion } from 'framer-motion';

export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      {[0, 1, 2].map(i => (
        <motion.div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-violet-400"
          animate={{ scale: [1, 1.5, 1], opacity: [0.4, 1, 0.4] }}
          transition={{
            duration: 1,
            repeat: Infinity,
            delay: i * 0.2,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
}
