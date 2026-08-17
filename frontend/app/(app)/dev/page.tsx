'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Code2, Play, Loader2, CheckCircle2, XCircle, Copy } from 'lucide-react';
import api from '@/lib/axios';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const ENDPOINTS = [
  { method: 'GET', path: '/health/live', auth: false, body: null, desc: 'Liveness probe' },
  { method: 'GET', path: '/health/ready', auth: false, body: null, desc: 'Readiness probe' },
  { method: 'GET', path: '/metrics', auth: true, body: null, desc: 'API request metrics' },
  { method: 'GET', path: '/mcp/status', auth: true, body: null, desc: 'MCP platform status' },
  { method: 'GET', path: '/mcp/tools', auth: true, body: null, desc: 'List all MCP tools' },
  { method: 'POST', path: '/auth/login', auth: false, body: JSON.stringify({ user_id: 'U1001', pin: '1234' }, null, 2), desc: 'Login and get JWT' },
  { method: 'POST', path: '/chat', auth: true, body: JSON.stringify({ message: 'What is my balance?', channel: 'web' }, null, 2), desc: 'Send message to AI agent' },
  { method: 'POST', path: '/verify', auth: true, body: JSON.stringify({ user_id: 'U1001', pin: '1234' }, null, 2), desc: 'Verify user identity' },
  { method: 'POST', path: '/faq/search', auth: true, body: JSON.stringify({ query: 'What is UPI Lite?', k: 3 }, null, 2), desc: 'Search knowledge base' },
];

export default function DevConsolePage() {
  const [selectedEndpoint, setSelectedEndpoint] = useState(ENDPOINTS[0]);
  const [requestBody, setRequestBody] = useState('');
  const [response, setResponse] = useState<{ data: unknown; status: number; ms: number } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = (ep: typeof ENDPOINTS[0]) => {
    setSelectedEndpoint(ep);
    setRequestBody(ep.body ?? '');
    setResponse(null);
    setError(null);
  };

  const handleSend = async () => {
    setIsLoading(true);
    setError(null);
    const start = Date.now();
    try {
      let parsed: unknown = undefined;
      if (requestBody) {
        try { parsed = JSON.parse(requestBody); } catch { setError('Invalid JSON in request body'); setIsLoading(false); return; }
      }
      const res = selectedEndpoint.method === 'GET'
        ? await api.get(selectedEndpoint.path)
        : await api.post(selectedEndpoint.path, parsed);
      setResponse({ data: res.data, status: res.status, ms: Date.now() - start });
    } catch (err: unknown) {
      const axErr = err as { response?: { data: unknown; status: number } };
      if (axErr.response) {
        setResponse({ data: axErr.response.data, status: axErr.response.status, ms: Date.now() - start });
      } else {
        setError((err as Error).message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-4 lg:p-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center gap-2">
        <Code2 className="w-5 h-5 text-cyan-400" />
        <h2 className="text-xl font-semibold text-white">Developer Console</h2>
        <span className="text-xs px-2 py-0.5 rounded-full border border-cyan-500/20 text-cyan-400/60">API Playground</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-white/5 bg-white/[0.02] overflow-hidden">
          <div className="p-3 border-b border-white/5">
            <p className="text-xs text-white/30 uppercase tracking-widest">Endpoints</p>
          </div>
          <div className="p-2 space-y-1">
            {ENDPOINTS.map(ep => (
              <button
                key={ep.path + ep.method}
                onClick={() => handleSelect(ep)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-xs transition-all',
                  selectedEndpoint.path === ep.path && selectedEndpoint.method === ep.method
                    ? 'bg-white/8 text-white'
                    : 'text-white/40 hover:bg-white/4 hover:text-white/70',
                )}
              >
                <span className={cn(
                  'font-mono text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0',
                  ep.method === 'GET' ? 'bg-green-500/15 text-green-400' : 'bg-cyan-500/15 text-cyan-400',
                )}>{ep.method}</span>
                <span className="truncate font-mono">{ep.path}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-2xl border border-white/5 bg-white/[0.02]">
            <div className="flex items-center justify-between p-3 border-b border-white/5">
              <div className="flex items-center gap-2">
                <span className={cn(
                  'font-mono text-xs font-bold px-1.5 py-0.5 rounded',
                  selectedEndpoint.method === 'GET' ? 'bg-green-500/15 text-green-400' : 'bg-cyan-500/15 text-cyan-400',
                )}>{selectedEndpoint.method}</span>
                <span className="font-mono text-sm text-white">{selectedEndpoint.path}</span>
              </div>
              <button
                onClick={handleSend}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium transition-colors disabled:opacity-40"
              >
                {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                Send
              </button>
            </div>
            {selectedEndpoint.body && (
              <div className="p-3">
                <p className="text-xs text-white/30 mb-2">Request Body</p>
                <textarea
                  value={requestBody}
                  onChange={e => setRequestBody(e.target.value)}
                  className="w-full h-28 bg-black/20 rounded-xl p-3 font-mono text-xs text-white/80 border border-white/5 focus:outline-none focus:border-violet-500/30 resize-none"
                />
              </div>
            )}
          </div>

          {response && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-white/5 bg-white/[0.02]"
            >
              <div className="flex items-center justify-between p-3 border-b border-white/5">
                <div className="flex items-center gap-2">
                  {response.status < 400
                    ? <CheckCircle2 className="w-4 h-4 text-green-400" />
                    : <XCircle className="w-4 h-4 text-red-400" />}
                  <span className={`text-sm font-mono ${response.status < 400 ? 'text-green-400' : 'text-red-400'}`}>{response.status}</span>
                  <span className="text-xs text-white/30">{response.ms}ms</span>
                </div>
                <button
                  onClick={() => { navigator.clipboard.writeText(JSON.stringify(response.data, null, 2)); toast.success('Copied!'); }}
                  className="text-white/20 hover:text-white/60 transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="p-3 overflow-auto max-h-64">
                <pre className="font-mono text-xs text-white/70 whitespace-pre-wrap">
                  {JSON.stringify(response.data, null, 2)}
                </pre>
              </div>
            </motion.div>
          )}

          {error && (
            <div className="p-3 rounded-xl border border-red-500/20 bg-red-500/8 text-xs text-red-400">{error}</div>
          )}
        </div>
      </div>
    </div>
  );
}
