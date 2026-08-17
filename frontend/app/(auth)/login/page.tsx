// Login page — premium dark banking auth experience.
// Design references: Revolut, CRED, Stripe.
// Key decisions:
// 1. PinDotInput instead of text field — more secure feel, banking-appropriate
// 2. Animated error shake on wrong credentials
// 3. Biometric + Passkey as Coming Soon placeholders (shows product roadmap)
// 4. Remember Device toggle with persistent auth hint
'use client';
import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Zap, Fingerprint, Key, AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import Link from 'next/link';
import { toast } from 'sonner';

import { authApi, chatApi } from '@/lib/api';
import { useAuth } from '@/components/providers/AuthProvider';
import { PinDotInput } from '@/features/auth/components/PinDotInput';
import { cn } from '@/lib/utils';

const loginSchema = z.object({
  user_id: z.string().min(1, 'User ID is required').regex(/^U\d+$/, 'User ID must be like U1001'),
  pin: z.string().length(4, 'PIN must be exactly 4 digits').regex(/^\d+$/, 'PIN must be numeric'),
});

type LoginForm = z.infer<typeof loginSchema>;

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, verify } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [rememberDevice, setRememberDevice] = useState(false);
  const [showUserId, setShowUserId] = useState(false);

  const expiredReason = searchParams.get('reason');

  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { user_id: '', pin: '' },
  });

  const pinValue = form.watch('pin');

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      // Step 1: Get JWT tokens
      const tokenRes = await authApi.login({ user_id: data.user_id, pin: data.pin });
      login(tokenRes);

      // Step 2: Create verified session (banking ops require session_id)
      const verifyRes = await chatApi.verify({ user_id: data.user_id, pin: data.pin });
      if (verifyRes.verified && verifyRes.session_id) {
        verify(verifyRes.session_id, verifyRes.first_name);
      }

      if (rememberDevice) {
        localStorage.setItem('auth_user', JSON.stringify({ userId: data.user_id, role: 'customer' }));
      }

      toast.success('Welcome back!', { description: `Signed in as ${data.user_id}` });
      // Redirect to AI Assistant — the default landing page after login
      router.push('/assistant');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Invalid credentials. Please check your User ID and PIN.';
      setAuthError(msg);
      form.setValue('pin', '');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[hsl(222,47%,6%)] flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-violet-600/8 blur-[100px] rounded-full pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-10">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-violet-500/25">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-semibold tracking-tight text-white">Nexus Banking</span>
        </div>

        {/* Session expired banner */}
        <AnimatePresence>
          {expiredReason === 'session_expired' && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mb-6 flex items-center gap-3 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-sm"
            >
              <AlertCircle className="w-4 h-4 shrink-0" />
              Your session expired. Please sign in again.
            </motion.div>
          )}
        </AnimatePresence>

        {/* Card */}
        <div className="p-8 rounded-2xl border border-white/8 bg-white/[0.03] backdrop-blur-sm">
          <h1 className="text-2xl font-bold text-white mb-1">Welcome back</h1>
          <p className="text-sm text-white/40 mb-8">Sign in to your AI banking platform</p>

          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            {/* User ID */}
            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">User ID</label>
              <div className="relative">
                <input
                  {...form.register('user_id')}
                  type={showUserId ? 'text' : 'password'}
                  placeholder="e.g. U1001"
                  autoComplete="username"
                  disabled={isLoading}
                  className={cn(
                    'w-full px-4 py-3 rounded-xl bg-white/5 border text-white placeholder:text-white/20',
                    'focus:outline-none focus:ring-2 focus:ring-violet-500/50 transition-all',
                    form.formState.errors.user_id
                      ? 'border-red-500/50'
                      : 'border-white/10 focus:border-violet-500/50',
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowUserId(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                >
                  {showUserId ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {form.formState.errors.user_id && (
                <p className="text-xs text-red-400 mt-1">{form.formState.errors.user_id.message}</p>
              )}
            </div>

            {/* PIN */}
            <div>
              <label className="block text-sm font-medium text-white/70 mb-4">4-Digit PIN</label>
              <div className="flex justify-center">
                <PinDotInput
                  value={pinValue}
                  onChange={v => form.setValue('pin', v, { shouldValidate: true })}
                  disabled={isLoading}
                  error={!!form.formState.errors.pin || !!authError}
                />
              </div>
              {form.formState.errors.pin && (
                <p className="text-xs text-red-400 mt-3 text-center">{form.formState.errors.pin.message}</p>
              )}
            </div>

            {/* Error */}
            <AnimatePresence>
              {authError && (
                <motion.div
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
                >
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {authError}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Remember Device */}
            <label className="flex items-center gap-3 cursor-pointer group">
              <div
                onClick={() => setRememberDevice(v => !v)}
                className={cn(
                  'w-10 h-5 rounded-full transition-colors relative flex-shrink-0',
                  rememberDevice ? 'bg-violet-600' : 'bg-white/10',
                )}
              >
                <div className={cn(
                  'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all',
                  rememberDevice ? 'left-5' : 'left-0.5',
                )} />
              </div>
              <span className="text-sm text-white/50 group-hover:text-white/70 transition-colors">Remember this device</span>
            </label>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading || pinValue.length !== 4}
              className={cn(
                'w-full py-3 rounded-xl font-semibold transition-all text-white',
                'bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed',
                'shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30',
                'flex items-center justify-center gap-2',
              )}
            >
              {isLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Signing in...</>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-white/8" />
            <span className="text-xs text-white/25 uppercase tracking-widest">Coming Soon</span>
            <div className="flex-1 h-px bg-white/8" />
          </div>

          {/* Biometric / Passkey placeholders */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { icon: Fingerprint, label: 'Biometric Login' },
              { icon: Key, label: 'Passkey' },
            ].map(({ icon: Icon, label }) => (
              <button
                key={label}
                type="button"
                disabled
                className="flex items-center justify-center gap-2 py-2.5 rounded-xl border border-white/6 text-white/25 text-sm cursor-not-allowed"
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Demo hint */}
        <p className="text-center text-xs text-white/20 mt-6">
          Demo: Use <code className="text-white/40">U1001</code> with PIN <code className="text-white/40">1111</code>
        </p>
      </motion.div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[hsl(222,47%,6%)] text-white flex items-center justify-center text-sm text-white/40">Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}
