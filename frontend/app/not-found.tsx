'use client';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { AlertCircle, ArrowLeft, Home } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[hsl(222,47%,6%)] text-white flex items-center justify-center p-6 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md space-y-6"
      >
        <div className="w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mx-auto text-violet-400">
          <AlertCircle className="w-8 h-8" />
        </div>

        <div>
          <h1 className="text-4xl font-bold font-mono tracking-tight text-white mb-2">404</h1>
          <h2 className="text-lg font-medium text-white/80">Page Not Found</h2>
          <p className="text-sm text-white/40 mt-2 leading-relaxed">
            The page or financial resource you are looking for does not exist or has been moved.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          <Link
            href="/assistant"
            className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
          >
            <Home className="w-4 h-4" /> Go to Assistant
          </Link>
          <button
            onClick={() => window.history.back()}
            className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-white/10 hover:bg-white/5 text-white/70 text-sm font-medium transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Go Back
          </button>
        </div>
      </motion.div>
    </div>
  );
}
