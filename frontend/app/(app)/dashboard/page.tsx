// Dashboard — AI-first layout. The mini chat bar appears at the top to reinforce
// that AI is the primary way to interact with banking data.
// Design: dark cards with gradient accents, animated counters, area chart.
'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowRight, TrendingUp, TrendingDown, Shield, CreditCard,
  AlertTriangle, Brain, Zap, ArrowUpRight, ArrowDownLeft, Clock,
} from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { AnimatedCounter } from '@/components/shared/AnimatedCounter';
import { formatCurrencyFromFloat } from '@/lib/utils';
import {
  AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip,
} from 'recharts';

// Mock spending data for chart — in production this comes from /account/history
const SPENDING_DATA = [
  { month: 'Mar', spending: 12400, income: 45000 },
  { month: 'Apr', spending: 15200, income: 45000 },
  { month: 'May', spending: 11800, income: 47000 },
  { month: 'Jun', spending: 18600, income: 47000 },
  { month: 'Jul', spending: 14200, income: 48000 },
  { month: 'Aug', spending: 16800, income: 48000 },
];

const AI_INSIGHTS = [
  { icon: TrendingUp, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20', text: 'Spending up 18% this month vs last month' },
  { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20', text: 'One suspicious transaction detected — review recommended' },
  { icon: Clock, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20', text: 'Electricity bill due in 3 days (₹1,200 est.)' },
];

const RECENT_TX = [
  { id: 'T1', desc: 'Amazon India', amount: -2499, type: 'debit', category: 'Shopping', date: 'Today' },
  { id: 'T2', desc: 'Salary Credit', amount: 48000, type: 'credit', category: 'Income', date: 'Yesterday' },
  { id: 'T3', desc: 'Swiggy', amount: -340, type: 'debit', category: 'Food', date: 'Yesterday' },
  { id: 'T4', desc: 'Netflix', amount: -649, type: 'debit', category: 'Entertainment', date: '2 days ago' },
  { id: 'T5', desc: 'HDFC ATM', amount: -5000, type: 'debit', category: 'Cash', date: '3 days ago' },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [aiQuery, setAiQuery] = useState('');

  const handleAiQuery = () => {
    if (!aiQuery.trim()) return;
    router.push(`/assistant?q=${encodeURIComponent(aiQuery)}`);
  };

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 18) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-white">
          {greeting()}, {user?.firstName ?? user?.userId ?? 'there'} 👋
        </h2>
        <p className="text-sm text-white/40 mt-0.5">Here is your financial overview</p>
      </div>

      {/* AI chat bar — clicking routes to /assistant rather than inline so the
          full conversational UI (streaming, history) is always available */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex items-center gap-3 p-3.5 rounded-2xl border border-violet-500/20 bg-violet-500/5 hover:border-violet-500/30 transition-colors cursor-pointer"
        onClick={() => router.push('/assistant')}
      >
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
          <Zap className="w-4 h-4 text-white" />
        </div>
        <span className="text-sm text-white/40 flex-1">Ask anything about your banking…</span>
        <ArrowRight className="w-4 h-4 text-white/20" />
      </motion.div>

      {/* Suggested quick prompts — pre-seed user intent */}
      <div className="flex flex-wrap gap-2">
        {['Show my last 5 transactions', 'Why was my card blocked?', 'What is UPI Lite?'].map(p => (
          <button
            key={p}
            onClick={() => router.push('/assistant')}
            className="text-xs px-3 py-1.5 rounded-lg border border-white/8 text-white/40 hover:text-white/70 hover:bg-white/5 transition-all"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Balance', value: 24500, prefix: '₹', color: 'from-violet-500/20 to-transparent', icon: TrendingUp, iconColor: 'text-violet-400' },
          { label: 'Available', value: 23200, prefix: '₹', color: 'from-cyan-500/20 to-transparent', icon: TrendingUp, iconColor: 'text-cyan-400' },
          { label: 'Cards Active', value: 2, prefix: '', color: 'from-green-500/20 to-transparent', icon: CreditCard, iconColor: 'text-green-400' },
          { label: 'Fraud Alerts', value: 1, prefix: '', color: 'from-red-500/20 to-transparent', icon: Shield, iconColor: 'text-red-400' },
        ].map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.08 }}
            className="p-4 rounded-2xl border border-white/5 bg-white/[0.03] hover:bg-white/[0.05] transition-colors relative overflow-hidden card-hover"
          >
            <div className={`absolute inset-0 bg-gradient-to-br ${card.color} pointer-events-none`} />
            <div className="relative">
              <card.icon className={`w-4 h-4 ${card.iconColor} mb-3`} />
              <div className="text-xl font-bold text-white font-mono">
                {card.prefix}<AnimatedCounter value={card.value} decimals={0} />
              </div>
              <p className="text-xs text-white/40 mt-0.5">{card.label}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Main content: chart + insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Spending chart */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 p-5 rounded-2xl border border-white/5 bg-white/[0.02]"
        >
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-medium text-white text-sm">Spending Trend</h3>
            <span className="text-xs text-white/30">Last 6 months</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={SPENDING_DATA} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(258,85%,62%)" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="hsl(258,85%,62%)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="incomeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(142,70%,45%)" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="hsl(142,70%,45%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="month" tick={{ fill: 'hsl(222,20%,50%)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'hsl(222,20%,50%)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: 'hsl(222,42%,12%)', border: '1px solid hsl(222,25%,18%)', borderRadius: '8px', fontSize: '12px' }}
                labelStyle={{ color: 'hsl(0,0%,80%)' }}
              />
              <Area type="monotone" dataKey="spending" stroke="hsl(258,85%,62%)" strokeWidth={2} fill="url(#spendGrad)" name="Spending" />
              <Area type="monotone" dataKey="income" stroke="hsl(142,70%,45%)" strokeWidth={2} fill="url(#incomeGrad)" name="Income" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* AI Insights */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]"
        >
          <div className="flex items-center gap-2 mb-4">
            <Brain className="w-4 h-4 text-violet-400" />
            <h3 className="font-medium text-white text-sm">AI Insights</h3>
          </div>
          <div className="space-y-3">
            {AI_INSIGHTS.map((insight, i) => (
              <div key={i} className={`p-3 rounded-xl border text-xs ${insight.bg} flex items-start gap-2`}>
                <insight.icon className={`w-3.5 h-3.5 ${insight.color} flex-shrink-0 mt-0.5`} />
                <span className="text-white/60 leading-relaxed">{insight.text}</span>
              </div>
            ))}
          </div>
          <button
            onClick={() => router.push('/assistant')}
            className="w-full mt-4 py-2 rounded-xl border border-violet-500/20 text-xs text-violet-400 hover:bg-violet-500/5 transition-colors flex items-center justify-center gap-1.5"
          >
            <Zap className="w-3 h-3" /> Ask AI for more insights
          </button>
        </motion.div>
      </div>

      {/* Recent Transactions */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.55 }}
        className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-white text-sm">Recent Transactions</h3>
          <button onClick={() => router.push('/transactions')} className="text-xs text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-1">
            View all <ArrowRight className="w-3 h-3" />
          </button>
        </div>
        <div className="space-y-1">
          {RECENT_TX.map(tx => (
            <div key={tx.id} className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/[0.03] transition-colors group">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${tx.type === 'credit' ? 'bg-green-500/10' : 'bg-white/5'}`}>
                {tx.type === 'credit'
                  ? <ArrowDownLeft className="w-4 h-4 text-green-400" />
                  : <ArrowUpRight className="w-4 h-4 text-white/40" />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white/80 truncate">{tx.desc}</p>
                <p className="text-xs text-white/30">{tx.category} · {tx.date}</p>
              </div>
              <span className={`text-sm font-mono font-medium ${tx.type === 'credit' ? 'text-green-400' : 'text-white/70'}`}>
                {tx.type === 'credit' ? '+' : ''}₹{Math.abs(tx.amount).toLocaleString('en-IN')}
              </span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
