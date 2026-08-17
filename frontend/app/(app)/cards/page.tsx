'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Lock, Unlock, AlertTriangle, CreditCard, Eye, EyeOff, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { fraudApi } from '@/lib/api';
import { VerificationGate } from '@/features/auth/components/VerificationGate';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const MOCK_CARDS = [
  { id: 'CRD001', last4: '4521', type: 'VISA', name: 'VISHNU S', expiry: '12/28', status: 'active', variant: 'from-violet-600 via-purple-600 to-cyan-600' },
  { id: 'CRD002', last4: '8834', type: 'Mastercard', name: 'VISHNU S', expiry: '06/27', status: 'active', variant: 'from-slate-700 via-slate-600 to-slate-800' },
];

export default function CardsPage() {
  const { isVerified, sessionId } = useAuth();
  const [selectedCard, setSelectedCard] = useState(0);
  const [showVerify, setShowVerify] = useState(false);
  const [pendingAction, setPendingAction] = useState<'lock' | 'report' | null>(null);
  const [cardStatuses, setCardStatuses] = useState<Record<string, string>>({});
  const [showNumber, setShowNumber] = useState(false);
  const [isActing, setIsActing] = useState(false);

  const card = MOCK_CARDS[selectedCard];
  const status = cardStatuses[card.id] ?? card.status;

  const handleAction = (action: 'lock' | 'report') => {
    if (!isVerified) {
      setPendingAction(action);
      setShowVerify(true);
      return;
    }
    executeAction(action);
  };

  const executeAction = async (action: 'lock' | 'report') => {
    if (!sessionId) return;
    setIsActing(true);
    try {
      if (action === 'lock') {
        const res = await fraudApi.lockCard({ session_id: sessionId, card_id: card.id });
        if (res.status) {
          setCardStatuses(prev => ({ ...prev, [card.id]: res.status! }));
          toast.success(`Card ${card.last4} locked successfully`);
        }
      } else {
        toast.success('Card reported as lost/stolen. A new card will be issued.');
        setCardStatuses(prev => ({ ...prev, [card.id]: 'reported_lost' }));
      }
    } catch {
      toast.error('Action failed. Please try again.');
    } finally {
      setIsActing(false);
    }
  };

  return (
    <div className="p-4 lg:p-6 max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-semibold text-white">Cards</h2>

      <div className="flex gap-2">
        {MOCK_CARDS.map((c, i) => (
          <button
            key={c.id}
            onClick={() => setSelectedCard(i)}
            className={cn(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              i === selectedCard ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70',
            )}
          >
            ···· {c.last4}
          </button>
        ))}
      </div>

      <motion.div
        key={card.id}
        initial={{ opacity: 0, rotateY: -15 }}
        animate={{ opacity: 1, rotateY: 0 }}
        transition={{ type: 'spring', stiffness: 200, damping: 25 }}
        className={cn(
          'relative h-48 rounded-3xl bg-gradient-to-br p-6 overflow-hidden shadow-2xl',
          card.variant,
          status === 'locked' || status === 'reported_lost' ? 'opacity-60 grayscale' : '',
        )}
      >
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-8 right-8 w-48 h-48 rounded-full border border-white/20" />
          <div className="absolute top-16 right-16 w-32 h-32 rounded-full border border-white/15" />
        </div>

        <div className="relative flex flex-col h-full justify-between">
          <div className="flex items-center justify-between">
            <div className="w-10 h-7 rounded-md bg-yellow-400/80 flex items-center justify-center">
              <div className="w-6 h-4 rounded-sm bg-yellow-500/60" />
            </div>
            {status === 'locked' && (
              <span className="text-xs px-2 py-1 rounded-lg bg-black/30 text-white/80 flex items-center gap-1">
                <Lock className="w-3 h-3" /> Locked
              </span>
            )}
            {status === 'reported_lost' && (
              <span className="text-xs px-2 py-1 rounded-lg bg-red-500/40 text-white/80 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Reported
              </span>
            )}
          </div>

          <div>
            <div className="font-mono text-white text-lg tracking-widest mb-3">
              {showNumber ? `4532 8901 6754 ${card.last4}` : `●●●● ●●●● ●●●● ${card.last4}`}
            </div>
            <div className="flex items-end justify-between">
              <div>
                <p className="text-white/50 text-[10px] uppercase tracking-widest">Card Holder</p>
                <p className="text-white text-sm font-medium">{card.name}</p>
              </div>
              <div className="text-right">
                <p className="text-white/50 text-[10px] uppercase tracking-widest">Expires</p>
                <p className="text-white text-sm font-mono">{card.expiry}</p>
              </div>
              <p className="text-white font-semibold text-lg">{card.type}</p>
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-3 gap-3">
        <button
          onClick={() => setShowNumber(v => !v)}
          className="flex flex-col items-center gap-2 p-4 rounded-2xl border border-white/5 bg-white/2 hover:bg-white/5 transition-all text-sm text-white/50 hover:text-white/80"
        >
          {showNumber ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
          {showNumber ? 'Hide' : 'Show'} Number
        </button>

        <button
          onClick={() => handleAction('lock')}
          disabled={isActing || status === 'reported_lost'}
          className={cn(
            'flex flex-col items-center gap-2 p-4 rounded-2xl border transition-all text-sm disabled:opacity-40',
            status === 'locked'
              ? 'border-green-500/20 bg-green-500/5 text-green-400 hover:bg-green-500/10'
              : 'border-yellow-500/20 bg-yellow-500/5 text-yellow-400 hover:bg-yellow-500/10',
          )}
        >
          {status === 'locked' ? <Unlock className="w-5 h-5" /> : <Lock className="w-5 h-5" />}
          {status === 'locked' ? 'Unfreeze' : 'Freeze'}
        </button>

        <button
          onClick={() => handleAction('report')}
          disabled={isActing || status === 'reported_lost'}
          className="flex flex-col items-center gap-2 p-4 rounded-2xl border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 transition-all text-sm text-red-400 disabled:opacity-40"
        >
          <AlertTriangle className="w-5 h-5" />
          Report Lost
        </button>
      </div>

      <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-white text-sm">Trusted Devices</h3>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/30">Coming Soon</span>
        </div>
        <div className="space-y-3">
          {[
            { name: 'Pixel 10 Pro', last: 'Yesterday', icon: '📱' },
            { name: 'MacBook Air M3', last: '2 days ago', icon: '💻' },
          ].map(d => (
            <div key={d.name} className="flex items-center gap-3 opacity-50">
              <span className="text-xl">{d.icon}</span>
              <div>
                <p className="text-sm text-white/60">{d.name}</p>
                <p className="text-xs text-white/30">Last active: {d.last}</p>
              </div>
              <CheckCircle2 className="w-4 h-4 text-green-400 ml-auto" />
            </div>
          ))}
        </div>
      </div>

      <VerificationGate
        isOpen={showVerify}
        onClose={() => { setShowVerify(false); setPendingAction(null); }}
        onVerified={() => { if (pendingAction) executeAction(pendingAction); setPendingAction(null); }}
      />
    </div>
  );
}
