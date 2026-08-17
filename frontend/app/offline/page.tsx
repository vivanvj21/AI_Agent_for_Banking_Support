'use client';
import { motion } from 'framer-motion';
import { WifiOff, RefreshCw } from 'lucide-react';

export default function OfflinePage() {
  return (
    <div className="min-h-screen bg-[hsl(222,47%,6%)] text-white flex items-center justify-center p-6 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md space-y-6"
      >
        <div className="w-16 h-16 rounded-2xl bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center mx-auto text-yellow-400">
          <WifiOff className="w-8 h-8" />
        </div>

        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white mb-2">You are offline</h1>
          <p className="text-sm text-white/40 leading-relaxed">
            Please check your internet connection to continue using Nexus Banking.
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Retry Connection
        </button>
      </motion.div>
    </div>
  );
}
