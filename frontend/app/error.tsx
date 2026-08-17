'use client';
import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, AlertTriangle, Home } from 'lucide-react';
import Link from 'next/link';

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Unhandled UI error:', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-[hsl(222,47%,6%)] text-white flex items-center justify-center p-6 text-center">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md space-y-6"
      >
        <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto text-red-400">
          <AlertTriangle className="w-8 h-8" />
        </div>

        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white mb-2">Something went wrong</h1>
          <p className="text-sm text-white/40 leading-relaxed">
            An error occurred while rendering this component. Please try again or return home.
          </p>
          {error.message && (
            <div className="mt-4 p-3 rounded-xl bg-black/40 border border-white/5 font-mono text-xs text-red-400/80 text-left overflow-auto max-h-32">
              {error.message}
            </div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          <button
            onClick={() => reset()}
            className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Try Again
          </button>
          <Link
            href="/assistant"
            className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-white/10 hover:bg-white/5 text-white/70 text-sm font-medium transition-colors"
          >
            <Home className="w-4 h-4" /> Return Home
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
