import { Cpu, ShieldAlert, ShieldCheck, Activity, Terminal, ArrowUpRight } from 'lucide-react';
import { cn } from '../lib/utils';

export interface InterrogatorModel {
  id: string;
  name: string;
  provider: 'OpenAI' | 'Anthropic' | 'Local / Fine-Tuned' | 'Meta' | 'Mistral';
  modelId: string;
  status: 'LEAK_DETECTED' | 'CLEAN_BASELINE' | 'PROBING';
  canaryMatchPct: number;
  probesExecuted: number;
  latencyMs: number;
  lastTested: string;
  verbatimSnippet?: string;
  colorScheme?: 'red' | 'blue' | 'amber';
}

interface InterrogatorCardProps {
  model: InterrogatorModel;
  isActive: boolean;
  onClick: () => void;
  className?: string;
}

export default function InterrogatorCard({
  model,
  isActive,
  onClick,
  className,
}: InterrogatorCardProps) {
  const isThreat = model.status === 'LEAK_DETECTED';
  const colorScheme = model.colorScheme || (isThreat ? 'red' : 'blue');

  // Conditional cyber/neon glow classes based on state
  const glowClasses = isActive
    ? colorScheme === 'red'
      ? 'border-red-500 bg-red-950/30 shadow-[0_0_30px_rgba(220,38,38,0.45)] ring-1 ring-red-500/50'
      : 'border-cyan-400 bg-cyan-950/30 shadow-[0_0_30px_rgba(14,165,233,0.45)] ring-1 ring-cyan-400/50'
    : 'border-slate-800 bg-slate-900/90 hover:border-slate-700 hover:bg-slate-850/80 shadow-sm hover:shadow-md';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        'relative rounded-2xl border p-5 transition-all duration-300 cursor-pointer overflow-hidden group select-none',
        glowClasses,
        className
      )}
    >
      {/* Active Glowing Neon Accent Bar */}
      {isActive && (
        <div
          className={cn(
            'absolute top-0 left-0 right-0 h-1 animate-pulse',
            colorScheme === 'red'
              ? 'bg-gradient-to-r from-red-600 via-red-400 to-amber-500'
              : 'bg-gradient-to-r from-blue-600 via-cyan-400 to-teal-400'
          )}
        />
      )}

      {/* Top Header: Model Name & Status Pill */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <div
            className={cn(
              'p-2 rounded-xl border transition-colors',
              isActive
                ? colorScheme === 'red'
                  ? 'bg-red-500/20 text-red-400 border-red-500/40'
                  : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                : 'bg-slate-800/80 text-slate-400 border-slate-700 group-hover:text-slate-200'
            )}
          >
            <Cpu size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-100 font-mono tracking-tight">
                {model.name}
              </h3>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                {model.provider}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5">
              Target ID: <span className="text-slate-300">{model.modelId}</span>
            </p>
          </div>
        </div>

        {/* State / Status Badge */}
        <div className="flex flex-col items-end gap-1">
          <span
            className={cn(
              'text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border flex items-center gap-1.5 shadow-sm',
              isThreat
                ? 'bg-red-500/10 text-red-400 border-red-500/40'
                : model.status === 'PROBING'
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/40'
                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/40'
            )}
          >
            {isThreat ? (
              <>
                <ShieldAlert size={12} className="animate-pulse" />
                <span>LEAK DETECTED</span>
              </>
            ) : model.status === 'PROBING' ? (
              <>
                <Activity size={12} className="animate-spin" />
                <span>PROBING...</span>
              </>
            ) : (
              <>
                <ShieldCheck size={12} />
                <span>CLEAN BASELINE</span>
              </>
            )}
          </span>
          <span className="text-[10px] text-slate-500 font-mono">
            {model.lastTested}
          </span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-3 gap-2 py-2.5 my-2 border-y border-slate-800/80 bg-slate-950/40 rounded-xl px-3 font-mono text-xs">
        <div>
          <span className="text-[10px] text-slate-500 uppercase block font-medium">Match Rate</span>
          <span
            className={cn(
              'font-bold text-sm',
              model.canaryMatchPct > 70
                ? 'text-red-400'
                : model.canaryMatchPct > 0
                ? 'text-amber-400'
                : 'text-emerald-400'
            )}
          >
            {model.canaryMatchPct}%
          </span>
        </div>
        <div>
          <span className="text-[10px] text-slate-500 uppercase block font-medium">Probes Fired</span>
          <span className="font-bold text-sm text-slate-200">{model.probesExecuted}</span>
        </div>
        <div>
          <span className="text-[10px] text-slate-500 uppercase block font-medium">Latency</span>
          <span className="font-bold text-sm text-slate-400">{model.latencyMs}ms</span>
        </div>
      </div>

      {/* Snippet preview if leak detected */}
      {model.verbatimSnippet && (
        <div className="mt-2 p-2 rounded-lg bg-slate-950/80 border border-slate-800/80 font-mono text-[11px] text-slate-300">
          <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
            <span className="flex items-center gap-1 font-semibold text-red-400">
              <Terminal size={11} /> Leaked Canary Payload
            </span>
            <span className="text-[9px] uppercase tracking-wider text-slate-600">Verbatim Output</span>
          </div>
          <p className="line-clamp-2 text-slate-300 font-mono text-[10px]">
            &quot;{model.verbatimSnippet}&quot;
          </p>
        </div>
      )}

      {/* Bottom Hint */}
      <div className="flex items-center justify-between mt-3 text-[11px] font-mono text-slate-400">
        <span className="text-[10px] text-slate-500">
          {isActive ? '● Live Telemetry Selected' : 'Click to inspect neural logs'}
        </span>
        <div className="flex items-center gap-1 text-slate-400 group-hover:text-slate-200 transition-colors">
          <span>{isActive ? 'Interrogating' : 'View Stream'}</span>
          <ArrowUpRight size={13} />
        </div>
      </div>
    </div>
  );
}
