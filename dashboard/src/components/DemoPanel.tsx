import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getDemoStatus, resetDemo } from '../api/client';
import { AlertCircle, Flame, CheckCircle, RefreshCw } from 'lucide-react';
import HoldToConfirmButton from './HoldToConfirmButton';
import ApiStateNotice from './ApiStateNotice';

export default function DemoPanel() {
  const { data: demo, isLoading, error, lastUpdated } = usePoll(getDemoStatus, { cacheKey: 'getDemoStatus', intervalMs: 2000 });
  const [actionError, setActionError] = useState<string | null>(null);

  const handleReset = async () => {
    try {
      setActionError(null);
      await resetDemo();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to reset state');
    }
  };

  return (
    <section className="bg-slate-900 rounded-xl border border-slate-800 p-6 space-y-6">
      <ApiStateNotice isLoading={isLoading} error={error} hasData={Boolean(demo)} lastUpdated={lastUpdated} />
      {actionError && (
        <div className="p-3 rounded-lg bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-mono flex items-center gap-2">
          <AlertCircle size={14} className="text-red-400 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Header & Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-sans tracking-tight">
            System State & Local Lifecycle
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Live database state and neutral local execution lifecycle
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs flex items-center gap-2">
            <span className="text-slate-500">RUN:</span>
            <span className="text-cyan-400 font-bold">{demo?.run_id || 'IDLE'}</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs flex items-center gap-2">
            <span className="text-slate-500">PHASE:</span>
            <span className="text-emerald-400 font-bold">{demo?.phase || 'READY'}</span>
          </div>
        </div>
      </div>

      {/* Steps breakdown (if any steps exist) */}
      {demo?.steps && demo.steps.length > 0 ? (
        <div className="space-y-2.5">
          {demo.steps.map((step) => (
            <div key={step.id} className="flex items-start gap-4 p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div className="mt-0.5 shrink-0">
                {step.status === 'PASS' && <CheckCircle className="text-emerald-400" size={18} />}
                {step.status === 'PENDING' && <div className="w-4 h-4 rounded-full border-2 border-slate-700 mt-0.5" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-xs text-slate-200 font-sans">
                    Stage {step.id}: {step.name}
                  </span>
                  <span className="text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded border bg-slate-800 text-slate-400 border-slate-700">
                    {step.status}
                  </span>
                </div>
                {step.detail && (
                  <div className="mt-1 text-[11px] text-slate-400 font-mono break-words">{step.detail}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-between p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <RefreshCw size={16} />
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-200">Active Live Pipeline</div>
              <div className="text-[11px] text-slate-400 font-mono">Sessions and traffic stream directly into the local SQLite store without synthetic simulations.</div>
            </div>
          </div>
        </div>
      )}

      {/* Danger Zone Cordon with Hold-to-Confirm Button */}
      <div className="rounded-xl border border-red-500/30 bg-red-950/10 p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-red-500/20 pb-2">
          <div className="flex items-center gap-1.5 text-red-400 font-mono text-xs font-bold">
            <Flame size={14} />
            <span>State Lifecycle • Reset Control</span>
          </div>
          <span className="text-[10px] font-mono text-red-400/60 uppercase">Manual Intervention</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <p className="text-xs text-slate-400 font-mono">
            Resetting clears local database state and reinitializes a neutral session context.
          </p>
          <div className="flex items-center gap-2.5">
            <HoldToConfirmButton
              onConfirm={handleReset}
              confirmText="State Reset Complete"
            >
              Reset Database State
            </HoldToConfirmButton>
          </div>
        </div>
      </div>
    </section>
  );
}
