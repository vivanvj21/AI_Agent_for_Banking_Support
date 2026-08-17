// Landing page — the public-facing entry point.
// Design goal: immediately communicate "AI-first banking platform", not "banking app with chatbot".
// Uses motion/react for scroll-triggered animations.
import Link from 'next/link';
import { ArrowRight, Zap, Shield, Brain, TrendingUp, Sparkles, Lock } from 'lucide-react';

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[hsl(222,47%,6%)] text-white overflow-hidden">
      {/* NAV */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/5 backdrop-blur-xl bg-[hsl(222,47%,6%)]/80">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-lg tracking-tight">Nexus Banking</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-sm text-white/60 hover:text-white transition-colors">
              Sign In
            </Link>
            <Link
              href="/login"
              className="text-sm px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 transition-colors font-medium"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="relative pt-32 pb-20 px-6">
        {/* Background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-violet-600/10 blur-[120px] rounded-full pointer-events-none" />
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[400px] h-[200px] bg-cyan-500/10 blur-[80px] rounded-full pointer-events-none" />

        <div className="max-w-4xl mx-auto text-center relative">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 text-violet-300 text-sm font-medium mb-8">
            <Sparkles className="w-3.5 h-3.5" />
            Powered by Multi-Agent AI
          </div>

          {/* Headline */}
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 text-balance">
            Your bank, run by{' '}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-violet-400 via-cyan-400 to-violet-400">
              autonomous AI
            </span>
          </h1>

          <p className="text-lg md:text-xl text-white/50 mb-10 max-w-2xl mx-auto text-balance">
            Not a chatbot. An AI agent that understands your finances, detects fraud in real-time,
            and answers any question about your account — instantly.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/login"
              className="group flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl bg-violet-600 hover:bg-violet-500 transition-all font-medium text-white shadow-lg shadow-violet-500/25"
            >
              Launch Platform
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl border border-white/10 hover:border-white/20 hover:bg-white/5 transition-all font-medium"
            >
              API Docs
            </a>
          </div>
        </div>

        {/* Feature Grid */}
        <div className="max-w-5xl mx-auto mt-24 grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              icon: Brain,
              title: 'Multi-Agent Intelligence',
              desc: 'Supervisor, Account, Fraud, and Search agents work in concert to answer any banking query.',
              color: 'from-violet-500/20 to-violet-500/5',
              iconColor: 'text-violet-400',
            },
            {
              icon: Shield,
              title: 'Real-Time Fraud Detection',
              desc: 'AI-powered fraud analysis with instant card lock, transaction flagging, and support escalation.',
              color: 'from-red-500/20 to-red-500/5',
              iconColor: 'text-red-400',
            },
            {
              icon: TrendingUp,
              title: 'Intelligent Analytics',
              desc: 'Spending trends, merchant breakdowns, and AI-generated financial insights.',
              color: 'from-cyan-500/20 to-cyan-500/5',
              iconColor: 'text-cyan-400',
            },
            {
              icon: Lock,
              title: 'Enterprise Security',
              desc: 'Argon2id PIN hashing, JWT rotation, rate limiting, and RBAC with full audit trails.',
              color: 'from-green-500/20 to-green-500/5',
              iconColor: 'text-green-400',
            },
            {
              icon: Zap,
              title: 'Hybrid RAG Search',
              desc: 'BM25 + vector search with Reciprocal Rank Fusion for accurate policy and FAQ answers.',
              color: 'from-yellow-500/20 to-yellow-500/5',
              iconColor: 'text-yellow-400',
            },
            {
              icon: Sparkles,
              title: 'Long-Term Memory',
              desc: 'The AI remembers your preferences and past interactions across every conversation.',
              color: 'from-pink-500/20 to-pink-500/5',
              iconColor: 'text-pink-400',
            },
          ].map((f) => (
            <div
              key={f.title}
              className="p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors group"
            >
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center mb-4`}>
                <f.icon className={`w-5 h-5 ${f.iconColor}`} />
              </div>
              <h3 className="font-semibold mb-2 text-white/90">{f.title}</h3>
              <p className="text-sm text-white/40 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/5 py-8 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-white/30">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4" />
            <span>Nexus Banking — Autonomous AI Banking Platform</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="http://localhost:8000/docs" target="_blank" className="hover:text-white/60 transition-colors">API Docs</a>
            <a href="http://localhost:8000/health" target="_blank" className="hover:text-white/60 transition-colors">Health</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
