// CommandPalette — Ctrl+K global command search.
// Uses the cmdk library which provides accessible combobox behavior.
// This is a major portfolio differentiator — makes the app feel like Linear/Vercel.
'use client';
import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Command } from 'cmdk';
import { AnimatePresence, motion } from 'framer-motion';
import {
  MessageSquare, LayoutDashboard, Building2, CreditCard, Shield,
  BookOpen, BarChart3, Settings, Wrench, Code2, Zap, Search,
  Lock, AlertTriangle,
} from 'lucide-react';

const COMMANDS = [
  {
    group: 'AI',
    items: [
      { id: 'ask-ai', icon: MessageSquare, label: 'Ask the AI Assistant', href: '/assistant', color: 'text-violet-400' },
    ],
  },
  {
    group: 'Navigate',
    items: [
      { id: 'dashboard', icon: LayoutDashboard, label: 'Go to Dashboard', href: '/dashboard', color: 'text-white/60' },
      { id: 'accounts', icon: Building2, label: 'Go to Accounts', href: '/accounts', color: 'text-cyan-400' },
      { id: 'cards', icon: CreditCard, label: 'Go to Cards', href: '/cards', color: 'text-white/60' },
      { id: 'knowledge', icon: BookOpen, label: 'Search Knowledge Base', href: '/knowledge', color: 'text-green-400' },
      { id: 'analytics', icon: BarChart3, label: 'View Analytics', href: '/analytics', color: 'text-white/60' },
      { id: 'settings', icon: Settings, label: 'Settings', href: '/settings', color: 'text-white/60' },
    ],
  },
  {
    group: 'Actions',
    items: [
      { id: 'fraud', icon: AlertTriangle, label: 'Report Fraud', href: '/fraud', color: 'text-red-400' },
      { id: 'lock-card', icon: Lock, label: 'Lock My Card', href: '/cards', color: 'text-yellow-400' },
    ],
  },
  {
    group: 'Developer',
    items: [
      { id: 'admin', icon: Wrench, label: 'Admin Panel', href: '/admin', color: 'text-white/40' },
      { id: 'dev', icon: Code2, label: 'Developer Console', href: '/dev', color: 'text-white/40' },
    ],
  },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  // Listen for Ctrl+K / Cmd+K globally
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(v => !v);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  const handleSelect = useCallback((href: string) => {
    setOpen(false);
    router.push(href);
  }, [router]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60]"
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ type: 'spring', stiffness: 500, damping: 35 }}
            className="fixed top-[20%] left-1/2 -translate-x-1/2 z-[60] w-full max-w-lg"
          >
            <Command
              className="rounded-2xl border border-white/10 bg-[hsl(222,42%,10%)] shadow-2xl overflow-hidden"
              loop
            >
              <div className="flex items-center gap-3 px-4 py-3 border-b border-white/6">
                <Search className="w-4 h-4 text-white/30 flex-shrink-0" />
                <Command.Input
                  placeholder="Search or ask anything…"
                  className="flex-1 bg-transparent text-sm text-white placeholder:text-white/25 outline-none"
                />
                <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-white/8 text-white/25 font-mono">ESC</kbd>
              </div>

              <Command.List className="max-h-80 overflow-y-auto p-2">
                <Command.Empty className="py-6 text-center text-sm text-white/30">
                  No results found.
                </Command.Empty>

                {COMMANDS.map(group => (
                  <Command.Group
                    key={group.group}
                    heading={<span className="text-[10px] font-medium text-white/25 uppercase tracking-widest px-2 py-1 block">{group.group}</span>}
                  >
                    {group.items.map(item => (
                      <Command.Item
                        key={item.id}
                        value={item.label}
                        onSelect={() => handleSelect(item.href)}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-white/60 cursor-pointer aria-selected:bg-white/8 aria-selected:text-white transition-colors"
                      >
                        <item.icon className={`w-4 h-4 ${item.color}`} />
                        {item.label}
                      </Command.Item>
                    ))}
                  </Command.Group>
                ))}
              </Command.List>
            </Command>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
