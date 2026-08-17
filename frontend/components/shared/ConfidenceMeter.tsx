// ConfidenceMeter — gradient progress bar showing RAG retrieval confidence.
// Recruiter talking point: "The AI shows its confidence level on every answer."
// Score is normalized from [0,1] to [0,100] for display.
import { cn } from '@/lib/utils';

interface ConfidenceMeterProps {
  score: number; // 0 to 1
  showLabel?: boolean;
  className?: string;
}

export function ConfidenceMeter({ score, showLabel = true, className }: ConfidenceMeterProps) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'from-green-500 to-emerald-400' : pct >= 60 ? 'from-yellow-500 to-amber-400' : 'from-red-500 to-orange-400';

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="flex-1 h-1.5 rounded-full bg-white/8 overflow-hidden">
        <div
          className={cn('h-full rounded-full bg-gradient-to-r', color)}
          style={{ width: `${pct}%`, transition: 'width 0.8s ease-out' }}
        />
      </div>
      {showLabel && (
        <span className="text-[10px] font-mono text-white/40 w-8 text-right">{pct}%</span>
      )}
    </div>
  );
}
