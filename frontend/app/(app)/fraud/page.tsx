'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, Shield, FileText, Loader2, CheckCircle2, Lock } from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { fraudApi } from '@/lib/api';
import { VerificationGate } from '@/features/auth/components/VerificationGate';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export default function FraudCenterPage() {
  const { isVerified, sessionId } = useAuth();
  const [showVerify, setShowVerify] = useState(false);
  const [reportTxId, setReportTxId] = useState('');
  const [reportReason, setReportReason] = useState('');
  const [isReporting, setIsReporting] = useState(false);
  const [reported, setReported] = useState<string[]>([]);

  const handleReport = async () => {
    if (!sessionId || !reportTxId) return;
    setIsReporting(true);
    try {
      const res = await fraudApi.report({
        session_id: sessionId,
        transaction_id: reportTxId,
        reason: reportReason,
      });
      if (res.status) {
        setReported(prev => [...prev, reportTxId]);
        setReportTxId('');
        setReportReason('');
        toast.success('Fraud report submitted', { description: `Transaction ${reportTxId} has been flagged.` });
      }
    } catch {
      toast.error('Report failed. Please try again.');
    } finally {
      setIsReporting(false);
    }
  };

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3">
        <Shield className="w-5 h-5 text-red-400" />
        <h2 className="text-xl font-semibold text-white">Fraud Center</h2>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="p-4 rounded-2xl border border-red-500/25 bg-red-500/8 flex items-start gap-3"
      >
        <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-white">1 suspicious transaction detected</p>
          <p className="text-xs text-white/40 mt-1">
            Transaction TX8834 — ₹12,499 on Aug 15. Mark as fraud or confirm it was you.
          </p>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => { setReportTxId('TX8834'); setReportReason('Suspicious large transaction'); }}
              className="text-xs px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
            >
              Report as Fraud
            </button>
            <button className="text-xs px-3 py-1.5 rounded-lg bg-white/5 text-white/50 hover:bg-white/8 transition-colors">
              It was me
            </button>
          </div>
        </div>
      </motion.div>

      {!isVerified ? (
        <div className="p-8 rounded-2xl border border-white/5 bg-white/[0.02] text-center">
          <Lock className="w-8 h-8 text-white/20 mx-auto mb-3" />
          <p className="text-sm text-white/40 mb-4">Verify your identity to report fraud</p>
          <button onClick={() => setShowVerify(true)} className="px-5 py-2 rounded-xl bg-violet-600 text-white text-sm font-medium">
            Verify PIN
          </button>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]"
        >
          <div className="flex items-center gap-2 mb-5">
            <FileText className="w-4 h-4 text-white/40" />
            <h3 className="font-medium text-white text-sm">Report Fraudulent Transaction</h3>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs text-white/50 mb-2">Transaction ID</label>
              <input
                value={reportTxId}
                onChange={e => setReportTxId(e.target.value)}
                placeholder="e.g. TX1234"
                className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/8 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-violet-500/50"
              />
            </div>
            <div>
              <label className="block text-xs text-white/50 mb-2">Reason (optional)</label>
              <textarea
                value={reportReason}
                onChange={e => setReportReason(e.target.value)}
                placeholder="Describe why this looks suspicious..."
                rows={3}
                className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/8 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-violet-500/50 resize-none"
              />
            </div>
            <button
              onClick={handleReport}
              disabled={!reportTxId || isReporting}
              className={cn(
                'w-full py-3 rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition-all',
                'bg-red-600 hover:bg-red-500 text-white disabled:opacity-40',
              )}
            >
              {isReporting
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</>
                : <><AlertTriangle className="w-4 h-4" /> Submit Fraud Report</>
              }
            </button>
          </div>

          {reported.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs text-white/30">Reported transactions:</p>
              {reported.map(id => (
                <div key={id} className="flex items-center gap-2 text-xs text-green-400">
                  <CheckCircle2 className="w-3 h-3" /> {id} — Flagged for review
                </div>
              ))}
            </div>
          )}
        </motion.div>
      )}

      <VerificationGate isOpen={showVerify} onClose={() => setShowVerify(false)} onVerified={() => {}} />
    </div>
  );
}
