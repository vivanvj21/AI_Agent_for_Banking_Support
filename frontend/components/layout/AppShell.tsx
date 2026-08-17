// AppShell — the main protected layout wrapper.
// Composes Sidebar (desktop) + MobileBottomNav + TopBar + CommandPalette.
// Auth redirect: if not authenticated, bounces to /login.
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { MobileBottomNav } from './MobileBottomNav';
import { TopBar } from './TopBar';
import { CommandPalette } from '@/components/shared/CommandPalette';
import { useAuth } from '@/components/providers/AuthProvider';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[hsl(222,47%,6%)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 animate-pulse" />
          <div className="text-sm text-white/30">Loading...</div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-[hsl(222,47%,6%)] flex">
      <Sidebar />
      <CommandPalette />

      {/* Main content area — offset by sidebar width on desktop */}
      <div className="flex-1 flex flex-col lg:ml-60 min-h-screen">
        <TopBar onOpenCommand={() => setCommandOpen(true)} />
        <motion.main
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="flex-1 pb-20 lg:pb-0"
        >
          {children}
        </motion.main>
      </div>

      <MobileBottomNav />
    </div>
  );
}
