'use client';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { Activity, Cpu, Shield, Zap, Globe, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { metricsApi, healthApi, mcpApi } from '@/lib/api';
import { queryKeys } from '@/lib/query';

export default function AdminPage() {
  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: queryKeys.metrics(),
    queryFn: metricsApi.get,
    refetchInterval: 30000,
  });

  const { data: health } = useQuery({
    queryKey: queryKeys.readiness(),
    queryFn: healthApi.ready,
    refetchInterval: 15000,
  });

  const { data: mcpStatus } = useQuery({
    queryKey: queryKeys.mcpStatus(),
    queryFn: mcpApi.status,
    refetchInterval: 60000,
  });

  const { data: mcpTools } = useQuery({
    queryKey: queryKeys.mcpTools(),
    queryFn: mcpApi.tools,
  });

  const latencyData = metrics
    ? Object.entries(metrics.average_latency_ms).map(([name, ms]) => ({
        name: name.replace('_', ' '),
        ms: Math.round(ms),
      }))
    : [];

  const totalRequests = metrics
    ? Object.values(metrics.request_counts).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-2">
        <Activity className="w-5 h-5 text-violet-400" />
        <h2 className="text-xl font-semibold text-white">Admin Panel</h2>
        <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/15 text-green-400">Live</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Total Requests', value: totalRequests.toString(), icon: Globe, color: 'text-cyan-400' },
          { label: 'Uptime', value: metrics ? `${Math.round(metrics.uptime_seconds / 3600)}h` : '—', icon: Zap, color: 'text-green-400' },
          { label: 'MCP Tools', value: mcpTools?.tool_count?.toString() ?? '—', icon: Cpu, color: 'text-violet-400' },
          { label: 'System', value: health?.ready ? 'Ready' : 'Degraded', icon: Shield, color: health?.ready ? 'text-green-400' : 'text-red-400' },
        ].map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="p-4 rounded-2xl border border-white/5 bg-white/[0.02]"
          >
            <card.icon className={`w-4 h-4 ${card.color} mb-2`} />
            <div className="text-2xl font-bold text-white font-mono">
              {metricsLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : card.value}
            </div>
            <p className="text-xs text-white/30 mt-0.5">{card.label}</p>
          </motion.div>
        ))}
      </div>

      {health && (
        <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
          <h3 className="font-medium text-white text-sm mb-4">System Health Checks</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {Object.entries(health.checks).map(([key, status]) => (
              <div key={key} className="flex items-center gap-2">
                {status === 'ok'
                  ? <CheckCircle2 className="w-4 h-4 text-green-400" />
                  : <XCircle className="w-4 h-4 text-red-400" />}
                <span className="text-sm text-white/60 capitalize">{key.replace('_', ' ')}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-white/25 mt-3">Uptime: {health.uptime_seconds.toFixed(0)}s</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {latencyData.length > 0 && (
          <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
            <h3 className="font-medium text-white text-sm mb-4">Avg Latency (ms)</h3>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={latencyData} margin={{ left: -10 }}>
                <XAxis dataKey="name" tick={{ fill: 'hsl(222,20%,50%)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'hsl(222,20%,50%)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'hsl(222,42%,12%)', border: '1px solid hsl(222,25%,18%)', borderRadius: '8px', fontSize: '12px' }} />
                <Bar dataKey="ms" fill="hsl(258,85%,62%)" radius={[4, 4, 0, 0]} name="ms" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {mcpStatus && (
          <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
            <h3 className="font-medium text-white text-sm mb-4">MCP Platform</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-white/50">Status</span>
                <span className={`text-sm font-medium ${mcpStatus.status === 'ready' ? 'text-green-400' : 'text-yellow-400'}`}>
                  {mcpStatus.status}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-white/50">Servers Available</span>
                <span className="text-sm text-white">{mcpStatus.has_available_servers ? 'Yes' : 'No'}</span>
              </div>
              {mcpTools?.tools?.slice(0, 4).map(tool => (
                <div key={tool.name} className="flex items-center gap-2 text-xs">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
                  <span className="text-white/40">{tool.name}</span>
                  <span className="text-white/20 ml-auto">{tool.server}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
