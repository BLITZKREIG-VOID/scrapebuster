import { ShieldAlert, ShieldCheck, Activity, Terminal, Zap, Crosshair, Layers } from 'lucide-react';
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
  const isProbing = model.status === 'PROBING';

  // Determine accent based on status
  const accentBorderTop = isThreat
    ? 'border-t-red-500'
    : isProbing
    ? 'border-t-amber-500'
    : 'border-t-slate-700';

  const glowShadow = isThreat
    ? 'shadow-[0_8px_60px_rgba(239,68,68,0.12),0_2px_20px_rgba(239,68,68,0.08)]'
    : isProbing
    ? 'shadow-[0_8px_60px_rgba(245,158,11,0.08)]'
    : 'shadow-lg';

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
        // Base card: glassmorphism, generous sizing, accent top border
        'relative rounded-2xl border border-slate-800 border-t-2 bg-slate-900/40 backdrop-blur-xl',
        'transition-all duration-300 cursor-pointer overflow-hidden group select-none',
        'flex flex-col min-h-[320px]',
        accentBorderTop,
        isActive ? cn(glowShadow, 'ring-1 ring-white/5') : 'shadow-md hover:shadow-2xl hover:bg-slate-900/60',
        className
      )}
    >
      {/* ── Card Content ── */}
      <div className="p-7 flex flex-col flex-1 gap-6">

        {/* Header: Icon + Model Identity */}
        <div className="flex items-start gap-4">
          <div
            className={cn(
              'w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border transition-all duration-300',
              isThreat
                ? 'bg-red-500/10 text-red-400 border-red-500/20 shadow-[0_0_20px_rgba(239,68,68,0.15)]'
                : isProbing
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                : isActive
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-slate-800/60 text-slate-400 border-slate-700/50 group-hover:text-slate-200 group-hover:border-slate-600'
            )}
          >
            {isThreat ? (
              <ShieldAlert size={22} className={isActive ? 'animate-pulse' : ''} />
            ) : isProbing ? (
              <Activity size={22} className={isActive ? 'animate-spin' : ''} />
            ) : (
              <ShieldCheck size={22} />
            )}
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="text-xl font-semibold text-slate-100 leading-tight truncate tracking-tight">
              {model.name}
            </h3>
            <div className="flex items-center gap-2.5 mt-2">
              <span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800/80 text-slate-400 font-mono border border-slate-700/50">
                {model.provider}
              </span>
              <span className="text-sm text-slate-400 font-mono truncate">
                {model.modelId}
              </span>
            </div>
          </div>
        </div>

        {/* Status Badge */}
        <div
          className={cn(
            'inline-flex items-center gap-2 text-[11px] font-mono font-bold uppercase tracking-widest px-3.5 py-2 rounded-lg border w-fit',
            isThreat
              ? 'bg-red-950/40 text-red-400 border-red-500/20'
              : isProbing
              ? 'bg-amber-950/40 text-amber-400 border-amber-500/20'
              : 'bg-emerald-950/40 text-emerald-400 border-emerald-500/20'
          )}
        >
          {isThreat ? (
            <><ShieldAlert size={13} className="animate-pulse" /> Leak Detected</>
          ) : isProbing ? (
            <><Activity size={13} className="animate-spin" /> Probing...</>
          ) : (
            <><ShieldCheck size={13} /> Clean Baseline</>
          )}
        </div>

        {/* ── Massive Metrics Row ── */}
        <div className="flex items-end justify-between gap-4 py-2">
          {/* Canary Match */}
          <div className="flex flex-col items-start">
            <span className="text-[10px] text-slate-500 uppercase font-mono font-semibold tracking-widest flex items-center gap-1 mb-1">
              <Crosshair size={10} /> Match
            </span>
            <span
              className={cn(
                'text-4xl lg:text-5xl font-light tracking-tight font-mono',
                model.canaryMatchPct > 70
                  ? 'text-red-400'
                  : model.canaryMatchPct > 0
                  ? 'text-amber-400'
                  : 'text-emerald-400'
              )}
            >
              {model.canaryMatchPct}<span className="text-lg text-slate-500 ml-0.5">%</span>
            </span>
          </div>

          {/* Probes Executed */}
          <div className="flex flex-col items-center">
            <span className="text-[10px] text-slate-500 uppercase font-mono font-semibold tracking-widest flex items-center gap-1 mb-1">
              <Layers size={10} /> Probes
            </span>
            <span className="text-4xl lg:text-5xl font-light tracking-tight font-mono text-slate-200">
              {model.probesExecuted}
            </span>
          </div>

          {/* Latency */}
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-slate-500 uppercase font-mono font-semibold tracking-widest flex items-center gap-1 mb-1">
              <Zap size={10} /> Latency
            </span>
            <span className="text-4xl lg:text-5xl font-light tracking-tight font-mono text-slate-400">
              {model.latencyMs}<span className="text-lg text-slate-500 ml-0.5">ms</span>
            </span>
          </div>
        </div>

        {/* ── Canary Leak Terminal (only for leak-detected) ── */}
        {model.verbatimSnippet && (
          <div className="p-4 bg-black/50 rounded-lg border border-red-900/30">
            <div className="flex items-center gap-2 mb-2.5">
              <Terminal size={13} className="text-red-400" />
              <span className="text-[10px] text-red-400 font-mono font-bold uppercase tracking-widest">
                Intercepted Canary Payload
              </span>
            </div>
            <p className="text-[13px] text-slate-300 font-mono leading-relaxed line-clamp-3">
              &quot;{model.verbatimSnippet}&quot;
            </p>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="px-7 py-4 border-t border-slate-800/50 flex items-center justify-between bg-slate-950/20">
        <span className="text-xs text-slate-500 font-mono">
          {model.lastTested}
        </span>
        <span
          className={cn(
            'text-xs font-mono font-semibold tracking-wide transition-colors',
            isActive
              ? isThreat ? 'text-red-400' : isProbing ? 'text-amber-400' : 'text-emerald-400'
              : 'text-slate-500 group-hover:text-slate-300'
          )}
        >
          {isActive ? '● LIVE' : 'SELECT →'}
        </span>
      </div>
    </div>
  );
}
