'use client';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, ResponsiveContainer, Tooltip,
} from 'recharts';

const MONTHLY = [
  { m: 'Jan', spend: 9800, income: 45000 },
  { m: 'Feb', spend: 12100, income: 45000 },
  { m: 'Mar', spend: 10400, income: 45000 },
  { m: 'Apr', spend: 15200, income: 47000 },
  { m: 'May', spend: 11800, income: 47000 },
  { m: 'Jun', spend: 18600, income: 47000 },
  { m: 'Jul', spend: 14200, income: 48000 },
  { m: 'Aug', spend: 16800, income: 48000 },
];

const CATEGORIES = [
  { name: 'Food', value: 4200, color: 'hsl(198,92%,56%)' },
  { name: 'Shopping', value: 6800, color: 'hsl(258,85%,62%)' },
  { name: 'Transport', value: 2100, color: 'hsl(142,70%,45%)' },
  { name: 'Entertainment', value: 1800, color: 'hsl(316,72%,62%)' },
  { name: 'Utilities', value: 1900, color: 'hsl(38,92%,52%)' },
];

const MERCHANTS = [
  { name: 'Amazon', amount: 3200 },
  { name: 'Swiggy', amount: 2100 },
  { name: 'Netflix', amount: 649 },
  { name: 'Uber', amount: 1800 },
  { name: 'Zomato', amount: 1400 },
];

export default function AnalyticsPage() {
  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-6xl mx-auto">
      <h2 className="text-xl font-semibold text-white">Analytics</h2>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
        <h3 className="font-medium text-white text-sm mb-5">Cash Flow — Income vs Spending</h3>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={MONTHLY} margin={{ left: -20, right: 0, top: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="incomeG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(142,70%,45%)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="hsl(142,70%,45%)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="spendG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(258,85%,62%)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="hsl(258,85%,62%)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="m" tick={{ fill: 'hsl(222,20%,50%)', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: 'hsl(222,20%,50%)', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: 'hsl(222,42%,12%)', border: '1px solid hsl(222,25%,18%)', borderRadius: '8px', fontSize: '12px' }} />
            <Area type="monotone" dataKey="income" stroke="hsl(142,70%,45%)" strokeWidth={2} fill="url(#incomeG)" name="Income" />
            <Area type="monotone" dataKey="spend" stroke="hsl(258,85%,62%)" strokeWidth={2} fill="url(#spendG)" name="Spending" />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
          <h3 className="font-medium text-white text-sm mb-5">Category Breakdown</h3>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="50%" height={160}>
              <PieChart>
                <Pie data={CATEGORIES} dataKey="value" cx="50%" cy="50%" innerRadius={45} outerRadius={75} strokeWidth={0}>
                  {CATEGORIES.map((c, i) => <Cell key={i} fill={c.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {CATEGORIES.map(c => (
                <div key={c.name} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: c.color }} />
                  <span className="text-xs text-white/50">{c.name}</span>
                  <span className="text-xs text-white/70 ml-auto font-mono">₹{c.value.toLocaleString('en-IN')}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
          <h3 className="font-medium text-white text-sm mb-5">Top Merchants</h3>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={MERCHANTS} layout="vertical" margin={{ left: -10, right: 10 }}>
              <XAxis type="number" tick={{ fill: 'hsl(222,20%,50%)', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: 'hsl(222,20%,60%)', fontSize: 11 }} axisLine={false} tickLine={false} width={60} />
              <Tooltip contentStyle={{ background: 'hsl(222,42%,12%)', border: '1px solid hsl(222,25%,18%)', borderRadius: '8px', fontSize: '12px' }} />
              <Bar dataKey="amount" fill="hsl(258,85%,62%)" radius={[0, 4, 4, 0]} name="₹" />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      </div>
    </div>
  );
}
