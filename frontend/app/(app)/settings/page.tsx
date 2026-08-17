'use client';
import { useTheme } from 'next-themes';
import { motion } from 'framer-motion';
import { Moon, Sun, Bell, Shield, LogOut, User } from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/login');
    toast.success('Signed out successfully');
  };

  return (
    <div className="p-4 lg:p-6 max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-semibold text-white">Settings</h2>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
        <div className="flex items-center gap-3 mb-4">
          <User className="w-4 h-4 text-white/40" />
          <h3 className="font-medium text-white text-sm">Profile</h3>
        </div>
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center text-white font-bold">
            {user?.firstName?.[0] ?? user?.userId?.[0] ?? 'U'}
          </div>
          <div>
            <p className="font-medium text-white">{user?.firstName ?? user?.userId}</p>
            <p className="text-sm text-white/40">Customer · {user?.userId}</p>
          </div>
        </div>
      </motion.div>

      <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
        <div className="flex items-center gap-3 mb-4">
          <Moon className="w-4 h-4 text-white/40" />
          <h3 className="font-medium text-white text-sm">Appearance</h3>
        </div>
        <div className="flex gap-3">
          {[{ value: 'dark', icon: Moon, label: 'Dark' }, { value: 'light', icon: Sun, label: 'Light' }].map(t => (
            <button
              key={t.value}
              onClick={() => setTheme(t.value)}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm transition-all',
                theme === t.value
                  ? 'border-violet-500/50 bg-violet-500/10 text-violet-300'
                  : 'border-white/8 text-white/40 hover:text-white/70',
              )}
            >
              <t.icon className="w-4 h-4" /> {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
        <div className="flex items-center gap-3 mb-4">
          <Bell className="w-4 h-4 text-white/40" />
          <h3 className="font-medium text-white text-sm">Notifications</h3>
        </div>
        {[{ label: 'Fraud Alerts', enabled: true }, { label: 'Transaction Alerts', enabled: true }, { label: 'AI Recommendations', enabled: false }, { label: 'Marketing', enabled: false }].map(n => (
          <div key={n.label} className="flex items-center justify-between py-3 border-b border-white/5 last:border-0">
            <span className="text-sm text-white/60">{n.label}</span>
            <div className={cn('w-10 h-5 rounded-full relative', n.enabled ? 'bg-violet-600' : 'bg-white/10')}>
              <div className={cn('absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all', n.enabled ? 'left-5' : 'left-0.5')} />
            </div>
          </div>
        ))}
      </div>

      <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="w-4 h-4 text-white/40" />
          <h3 className="font-medium text-white text-sm">Security</h3>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white/70">Two-Factor Authentication</p>
              <p className="text-xs text-white/30">Coming Soon</p>
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-white/25">Soon</span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white/70">Biometric Login</p>
              <p className="text-xs text-white/30">Coming Soon</p>
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-white/25">Soon</span>
          </div>
        </div>
      </div>

      <button
        onClick={handleLogout}
        className="w-full py-3 rounded-2xl border border-red-500/20 text-red-400 hover:bg-red-500/8 transition-colors flex items-center justify-center gap-2 text-sm font-medium"
      >
        <LogOut className="w-4 h-4" /> Sign Out
      </button>
    </div>
  );
}
