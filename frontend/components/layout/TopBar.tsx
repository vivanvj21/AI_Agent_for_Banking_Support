// TopBar — sticky header shown on all protected pages.
// Contains: page title, search/command palette trigger, notification bell, user avatar.
'use client';
import { usePathname } from 'next/navigation';
import { Search, Bell, User } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/components/providers/AuthProvider';

const PAGE_TITLES: Record<string, string> = {
  '/assistant': 'AI Assistant',
  '/dashboard': 'Dashboard',
  '/accounts': 'Accounts',
  '/cards': 'Cards',
  '/fraud': 'Fraud Center',
  '/knowledge': 'Knowledge Base',
  '/analytics': 'Analytics',
  '/admin': 'Admin Panel',
  '/dev': 'Developer Console',
  '/settings': 'Settings',
  '/profile': 'Profile',
  '/notifications': 'Notifications',
};

interface TopBarProps {
  onOpenCommand?: () => void;
}

export function TopBar({ onOpenCommand }: TopBarProps) {
  const pathname = usePathname();
  const { user } = useAuth();

  const title = Object.entries(PAGE_TITLES).find(([k]) =>
    pathname === k || pathname.startsWith(k + '/'),
  )?.[1] ?? 'Nexus Banking';

  return (
    <header className="sticky top-0 z-20 h-14 flex items-center justify-between px-4 lg:px-6 border-b border-white/5 bg-[hsl(222,47%,6%)]/90 backdrop-blur-xl">
      {/* Page title — desktop shows this, mobile shows logo */}
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-white/80 hidden lg:block">{title}</h1>
      </div>

      <div className="flex items-center gap-2">
        {/* Command palette trigger */}
        <button
          onClick={onOpenCommand}
          className={cn(
            'hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-white/30',
            'border border-white/6 bg-white/2 hover:bg-white/5 hover:text-white/60 transition-all',
          )}
        >
          <Search className="w-3.5 h-3.5" />
          <span>Search or ask...</span>
          <kbd className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-white/8 text-white/25 font-mono">⌘K</kbd>
        </button>

        {/* Notification bell */}
        <button className="relative w-8 h-8 rounded-lg flex items-center justify-center text-white/30 hover:text-white/70 hover:bg-white/5 transition-all">
          <Bell className="w-4 h-4" />
          {/* Unread dot */}
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-red-500" />
        </button>

        {/* User avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center text-xs font-bold text-white cursor-pointer hover:opacity-80 transition-opacity">
          {user?.firstName?.[0] ?? user?.userId?.[0] ?? 'U'}
        </div>
      </div>
    </header>
  );
}
