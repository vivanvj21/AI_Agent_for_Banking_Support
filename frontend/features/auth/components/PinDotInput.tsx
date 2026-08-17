// PinDotInput — 4-digit PIN entry with masked dot display.
// We use a hidden <input> with maxLength=4 to capture keyboard input,
// while displaying large dot indicators for each digit.
// This approach avoids custom key handling and is accessible by default.
'use client';
import { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface PinDotInputProps {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  error?: boolean;
}

export function PinDotInput({ value, onChange, disabled, error }: PinDotInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);

  return (
    <div
      className="flex flex-col items-center gap-4"
      onClick={() => inputRef.current?.focus()}
    >
      {/* Hidden real input */}
      <input
        ref={inputRef}
        type="password"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={4}
        value={value}
        onChange={e => onChange(e.target.value.replace(/\D/g, '').slice(0, 4))}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        disabled={disabled}
        className="sr-only"
        aria-label="4-digit PIN"
        autoComplete="current-password"
      />

      {/* Visual dot display */}
      <div className="flex items-center gap-4">
        {Array.from({ length: 4 }).map((_, i) => {
          const filled = i < value.length;
          const active = focused && i === value.length;
          return (
            <motion.div
              key={i}
              animate={{
                scale: filled ? 1 : active ? 1.2 : 1,
              }}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
              className={cn(
                'w-4 h-4 rounded-full border-2 transition-colors duration-200',
                filled
                  ? error
                    ? 'bg-red-500 border-red-500'
                    : 'bg-violet-500 border-violet-500'
                  : active
                  ? 'border-violet-400 bg-transparent'
                  : 'border-white/20 bg-transparent',
              )}
            />
          );
        })}
      </div>

      {/* Active indicator ring around the whole input */}
      <div
        className={cn(
          'absolute inset-0 rounded-2xl pointer-events-none transition-opacity duration-200',
          focused ? 'opacity-100' : 'opacity-0',
        )}
        style={{ boxShadow: '0 0 0 2px hsl(258 85% 62% / 0.3)' }}
      />
    </div>
  );
}
