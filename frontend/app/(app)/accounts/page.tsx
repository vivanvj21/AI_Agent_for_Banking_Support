'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Building2, ArrowDownLeft, ArrowUpRight, Lock, RefreshCw } from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { useQuery } from '@tanstack/react-query';
import { accountApi } from '@/lib/api';
import { queryKeys } from '@/lib/query';
import { AnimatedCounter } from '@/components/shared/AnimatedCounter';
import { VerificationGate } from '@/features/auth/components/VerificationGate';

export default function AccountsPage() {
  const { isVerified, sessionId } = useAuth();
  const [showVerify, setShowVerify] = useState(false);

  const { data: balance, isLoading, refetch } = useQuery({
    queryKey: queryKeys.balance(sessionId ?? ''),
    queryFn: () => accountApi.balance({ session_id: sessionId! }),
    enabled: isVerified && !!sessionId,
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: queryKeys.transactions(sessionId ?? '', 20),
    queryFn: () => accountApi.history({ session_id: sessionId!, limit: 20 }),
    enabled: isVerified && !!sessionId,
  });

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Accounts</h2>
        {isVerified && (
          <button onClick={() => refetch()} className="text-white/30 hover:text-white/60 transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        )}
      </div>

      {!isVerified && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="p-8 rounded-2xl border border-white/5 bg-white/[0.02] text-center"
        >
          <Lock className="w-10 h-10 text-white/20 mx-auto mb-4" />
          <h3 className="font-medium text-white mb-2">Verification Required</h3>
          <p className="text-sm text-white/40 mb-6">Enter your PIN to view account details</p>
          <button
            onClick={() => setShowVerify(true)}
            className="px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
          >
            Verify Identity
          </button>
        </motion.div>
      )}

      {isVerified && (
        <>
          {isLoading ? (
            <div className="h-40 rounded-2xl shimmer" />
          ) : balance && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-6 rounded-2xl border border-white/5 bg-gradient-to-br from-violet-500/10 via-transparent to-cyan-500/5 relative overflow-hidden"
            >
              <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-violet-500/5 blur-3xl" />
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Building2 className="w-4 h-4 text-white/40" />
                    <span className="text-sm text-white/40">{balance.account_type ?? 'Savings Account'}</span>
                  </div>
                  <div className="text-4xl font-bold text-white font-mono">
                    ₹<AnimatedCounter value={balance.balance ?? 0} decimals={2} />
                  </div>
                  <p className="text-sm text-white/40 mt-1">
                    {balance.account_id ?? 'Primary Account'} · {balance.currency ?? 'INR'}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-white/30">Available Balance</p>
                  <p className="text-lg font-semibold text-green-400 font-mono">
                    ₹{((balance.balance ?? 0) * 0.95).toFixed(2)}
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          <div className="rounded-2xl border border-white/5 bg-white/[0.02] overflow-hidden">
            <div className="p-4 border-b border-white/5">
              <h3 className="font-medium text-white text-sm">Transaction History</h3>
            </div>
            {historyLoading ? (
              <div className="p-4 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-12 rounded-xl shimmer" />
                ))}
              </div>
            ) : (
              <div className="divide-y divide-white/3">
                {(history?.transactions ?? []).slice(0, 15).map(tx => (
                  <div key={tx.transaction_id} className="flex items-center gap-3 px-4 py-3 hover:bg-white/2 transition-colors">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${tx.type === 'credit' ? 'bg-green-500/10' : 'bg-white/4'}`}>
                      {tx.type === 'credit'
                        ? <ArrowDownLeft className="w-4 h-4 text-green-400" />
                        : <ArrowUpRight className="w-4 h-4 text-white/40" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white/80 truncate">{tx.description}</p>
                      <p className="text-xs text-white/30">{tx.date}</p>
                    </div>
                    {tx.flagged_fraud && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-red-500/15 text-red-400 border border-red-500/25">Fraud</span>
                    )}
                    <span className={`text-sm font-mono ${tx.type === 'credit' ? 'text-green-400' : 'text-white/70'}`}>
                      {tx.type === 'credit' ? '+' : '-'}₹{Math.abs(tx.amount).toLocaleString('en-IN')}
                    </span>
                  </div>
                ))}
                {(!history?.transactions?.length) && (
                  <div className="py-10 text-center text-sm text-white/25">No transactions found</div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      <VerificationGate
        isOpen={showVerify}
        onClose={() => setShowVerify(false)}
        onVerified={() => setShowVerify(false)}
      />
    </div>
  );
}
