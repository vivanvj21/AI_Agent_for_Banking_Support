// AgentBadge — color-coded pill showing which AI agent handled a request.
// Colors map to agent roles: Supervisor(violet), Account(cyan), Fraud(red), Search(green).
// Visible in AI chat messages to make multi-agent routing transparent.
import { cn } from '@/lib/utils';
import { Brain, Building2, Shield, BookOpen } from 'lucide-react';

type AgentType = 'supervisor' | 'account' | 'fraud' | 'search' | 'unknown';

interface AgentBadgeProps {
  agent: string;
  className?: string;
}

function getAgentConfig(agent: string): { type: AgentType; label: string; icon: React.ElementType; className: string } {
  const a = agent.toLowerCase();
  if (a.includes('supervisor')) return { type: 'supervisor', label: 'Supervisor', icon: Brain, className: 'bg-violet-500/15 text-violet-300 border-violet-500/25' };
  if (a.includes('account')) return { type: 'account', label: 'Account Agent', icon: Building2, className: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/25' };
  if (a.includes('fraud')) return { type: 'fraud', label: 'Fraud Agent', icon: Shield, className: 'bg-red-500/15 text-red-300 border-red-500/25' };
  if (a.includes('search') || a.includes('faq') || a.includes('rag')) return { type: 'search', label: 'Search Agent', icon: BookOpen, className: 'bg-green-500/15 text-green-300 border-green-500/25' };
  return { type: 'unknown', label: agent, icon: Brain, className: 'bg-white/5 text-white/40 border-white/10' };
}

export function AgentBadge({ agent, className }: AgentBadgeProps) {
  const config = getAgentConfig(agent);
  const Icon = config.icon;
  return (
    <span className={cn(
      'inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-md border',
      config.className,
      className,
    )}>
      <Icon className="w-2.5 h-2.5" />
      {config.label}
    </span>
  );
}
