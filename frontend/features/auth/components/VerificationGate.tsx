// VerificationGate — modal that prompts for PIN before banking operations.
// This component exists because /account/balance and /account/history
// require an ACTIVE verified session_id, but JWT login alone is not enough.
// We show this gate inline (modal) rather than redirecting to maintain context.
'use client';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Loader2, X } from 'lucide-react';
import { toast } from 'sonner';
import { chatApi } from '@/lib/api';
import { useAuth } from '@/components/providers/AuthProvider';
import { PinDotInput } from './PinDotInput';
import { cn } from '@/lib/utils';

interface VerificationGateProps {
  isOpen: boolean;
  onClose: () => void;
  onVerified: () => void;
}

export function VerificationGate({ isOpen, onClose, onVerified }: VerificationGateProps) {
  const { user, verify } = useAuth();
  const [pin, setPin] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async () => {
    if (pin.length !== 4 || !user) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await chatApi.verify({ user_id: user.userId, pin });
      if (res.verified && res.session_id) {
        verify(res.session_id, res.first_name);
        toast.success('Identity verified');
        onVerified();
        onClose();
      } else {
        setError(res.error ?? 'Verification failed. Check your PIN.');
        setPin('');
      }
    } catch {
      setError('Verification failed. Please try again.');
      setPin('');
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-submit when all 4 digits entered
  const handlePinChange = (v: string) => {
    setPin(v);
    setError(null);
    if (v.length === 4) setTimeout(() => handleVerify(), 100);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          />
          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
          >
            <div className="w-full max-w-sm p-8 rounded-2xl bg-[hsl(222,42%,10%)] border border-white/10 shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
                    <Shield className="w-5 h-5 text-violet-400" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-white">Verify Identity</h2>
                    <p className="text-xs text-white/40">Enter your PIN to continue</p>
                  </div>
                </div>
                <button onClick={onClose} className="text-white/30 hover:text-white/60 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <PinDotInput value={pin} onChange={handlePinChange} disabled={isLoading} error={!!error} />

              {error && (
                <p className="text-xs text-red-400 text-center mt-4">{error}</p>
              )}

              <button
                onClick={handleVerify}
                disabled={pin.length !== 4 || isLoading}
                className={cn(
                  'w-full mt-6 py-3 rounded-xl font-semibold text-white transition-all',
                  'bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed',
                  'flex items-center justify-center gap-2',
                )}
              >
                {isLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Verifying...</> : 'Confirm'}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
