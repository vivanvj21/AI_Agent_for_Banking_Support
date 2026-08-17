// MobileBottomNav — Revolut-style bottom tab bar for mobile.
// Shown only on screens < lg breakpoint.
// AI Assistant is the first tab.
'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import { MessageSquare, LayoutDashboard, CreditCard, Shield, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

const tabs = [
  { href: '/assistant', icon: MessageSquare, label: 'AI' },
  { href: '/dashboard', icon: LayoutDashboard, label: 'Home' },
  { href: '/cards', icon: CreditCard, label: 'Cards' },
  { href: '/fraud', icon: Shield, label: 'Fraud' },
  { href: '/analytics', icon: BarChart3, label: 'Analytics' },
];

export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-white/5 bg-[hsl(222,42%,8%)]/95 backdrop-blur-xl">
      <div className="flex items-center justify-around h-16 px-2">
        {tabs.map(tab => {
          const active = pathname === tab.href || (tab.href !== '/' && pathname.startsWith(tab.href));
          return (
            <Link key={tab.href} href={tab.href} className="flex-1">
              <motion.div
                whileTap={{ scale: 0.9 }}
                className="flex flex-col items-center justify-center gap-1 py-1"
              >
                <div className={cn(
                  'p-1.5 rounded-lg transition-colors',
                  active ? 'bg-violet-500/20' : '',
                )}>
                  <tab.icon className={cn(
                    'w-5 h-5 transition-colors',
                    active ? 'text-violet-400' : 'text-white/30',
                  )} />
                </div>
                <span className={cn(
                  'text-[10px] font-medium transition-colors',
                  active ? 'text-violet-400' : 'text-white/30',
                )}>{tab.label}</span>
              </motion.div>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
