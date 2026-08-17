// Sidebar — desktop navigation (hidden on mobile).
// Navigation order is AI-FIRST: Assistant appears before Dashboard.
// This is intentional — the AI assistant IS the product, not an add-on.
// Design: dark glass panel with active item highlight and hover states.
'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Zap, MessageSquare, LayoutDashboard, Building2, CreditCard,
  Shield, BookOpen, BarChart3, Settings, User, Wrench, Code2, LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/components/providers/AuthProvider';

const navItems = [
  { href: '/assistant', icon: MessageSquare, label: 'Assistant', badge: 'AI' },
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  null, // separator
  { href: '/accounts', icon: Building2, label: 'Accounts' },
  { href: '/cards', icon: CreditCard, label: 'Cards' },
  { href: '/fraud', icon: Shield, label: 'Fraud Center' },
  null,
  { href: '/knowledge', icon: BookOpen, label: 'Knowledge' },
  { href: '/analytics', icon: BarChart3, label: 'Analytics' },
];

const bottomItems = [
  { href: '/admin', icon: Wrench, label: 'Admin' },
  { href: '/dev', icon: Code2, label: 'Dev Console' },
  { href: '/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="hidden lg:flex flex-col w-60 min-h-screen bg-[hsl(222,42%,8%)] border-r border-white/5 fixed left-0 top-0 bottom-0 z-30">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-white/5 flex-shrink-0">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center">
          <Zap className="w-3.5 h-3.5 text-white" />
        </div>
        <span className="font-semibold text-white tracking-tight">Nexus Banking</span>
      </div>

      {/* Main Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto scrollbar-hide">
        {navItems.map((item, i) => {
          if (!item) return <div key={i} className="my-3 h-px bg-white/5" />;
          const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href}>
              <motion.div
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.98 }}
                className={cn(
                  'relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group',
                  active
                    ? 'text-white bg-white/8'
                    : 'text-white/40 hover:text-white/80 hover:bg-white/4',
                )}
              >
                {active && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full bg-violet-500"
                    transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                  />
                )}
                <item.icon className={cn('w-4 h-4 flex-shrink-0', active ? 'text-violet-400' : '')} />
                <span className="flex-1">{item.label}</span>
                {item.badge && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-violet-500/20 text-violet-300 font-medium">
                    {item.badge}
                  </span>
                )}
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* Bottom Items */}
      <div className="px-3 py-3 border-t border-white/5 space-y-0.5">
        {bottomItems.map(item => {
          const active = pathname.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href}>
              <div className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                active ? 'text-white bg-white/8' : 'text-white/30 hover:text-white/60 hover:bg-white/4',
              )}>
                <item.icon className="w-4 h-4" />
                {item.label}
              </div>
            </Link>
          );
        })}

        {/* User Card */}
        <div className="mt-3 flex items-center gap-3 px-3 py-2.5 rounded-lg border border-white/5 bg-white/2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
            {user?.firstName?.[0] ?? user?.userId?.[0] ?? 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-white truncate">{user?.firstName ?? user?.userId}</p>
            <p className="text-[10px] text-white/30">Customer</p>
          </div>
          <button onClick={logout} className="text-white/20 hover:text-red-400 transition-colors" title="Sign out">
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
