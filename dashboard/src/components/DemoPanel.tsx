import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getDemoStatus, runDemo, resetDemo, restoreGolden } from '../api/client';
import { Play, CheckCircle, XCircle, Loader2, AlertCircle, Flame } from 'lucide-react';
import HoldToConfirmButton from './HoldToConfirmButton';
import ApiStateNotice from './ApiStateNotice';

export default function DemoPanel() {
  const { data: demo, isLoading, error, lastUpdated } = usePoll(getDemoStatus, { cacheKey: 'getDemoStatus', intervalMs: 2000 });
  const [actionError, setActionError] = useState<string | null>(null);

  const handleRunNext = async () => {
    if (!demo || demo.steps?.some(s => s.status === 'RUNNING')) return;
    const nextStep = demo.steps?.find(s => s.status === 'PENDING');
    if (nextStep) {
      try {
        setActionError(null);
        await runDemo(nextStep.id);
      } catch (e) {
        setActionError(e instanceof Error ? e.message : 'Failed to advance demo step');
      }
    }
  };

  const handleRunAll = async () => {
    try {
      setActionError(null);
      await runDemo();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to execute automation matrix');
    }
  };

  const handleReset = async () => {
    try {
      setActionError(null);
      await resetDemo();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to reset demo state');
    }
  };

  const handleRestore = async () => {
    try {
      setActionError(null);
      await restoreGolden();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to restore golden dataset');
    }
  };

  const isRunning = demo?.steps?.some(s => s.status === 'RUNNING');
  const hasPending = demo?.steps?.some(s => s.status === 'PENDING');

  return (
    <section className="bg-slate-900 rounded-xl border border-slate-800 p-6 space-y-6">
      <ApiStateNotice isLoading={isLoading} error={error} hasData={Boolean(demo)} lastUpdated={lastUpdated} />
      {actionError && (
        <div className="p-3 rounded-lg bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-mono flex items-center gap-2">
          <AlertCircle size={14} className="text-red-400 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Header & Verb-First Automation Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-sans tracking-tight">
            Attack Vector Simulation & Demo Automation
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Step-by-step end-to-end execution of scraper intrusion and LLM provenance proof
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button 
            onClick={handleRunNext}
            disabled={isRunning || !hasPending}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-mono font-bold uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_12px_rgba(6,182,212,0.25)] cursor-pointer"
          >
            {isRunning ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            <span>Advance Demo Pipeline</span>
          </button>

          <button 
            onClick={handleRunAll}
            disabled={isRunning || !hasPending}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_12px_rgba(16,185,129,0.25)] cursor-pointer"
          >
            <Play size={13} fill="currentColor" />
            <span>Execute Full Automation Matrix</span>
          </button>
        </div>
      </div>

      {/* Step Breakdown */}
      <div className="space-y-2.5">
        {demo?.steps?.map((step) => (
          <div key={step.id} className="flex items-start gap-4 p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <div className="mt-0.5 shrink-0">
              {step.status === 'PASS' && <CheckCircle className="text-emerald-400" size={18} />}
              {step.status === 'FAIL' && <XCircle className="text-red-400" size={18} />}
              {step.status === 'RUNNING' && <Loader2 className="text-cyan-400 animate-spin" size={18} />}
              {step.status === 'PENDING' && <div className="w-4 h-4 rounded-full border-2 border-slate-700 mt-0.5" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-4">
                <span className="font-semibold text-xs text-slate-200 font-sans">
                  Stage {step.id}: {step.name}
                </span>
                <span className={`text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded border shrink-0 ${
                  step.status === 'PASS' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                  step.status === 'FAIL' ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                  step.status === 'RUNNING' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' :
                  'bg-slate-800 text-slate-400 border-slate-700'
                }`}>
                  {step.status}
                </span>
              </div>
              {step.detail && (
                <div className="mt-1 text-[11px] text-slate-400 font-mono break-words">{step.detail}</div>
              )}
            </div>
          </div>
        ))}
        {(!demo?.steps || demo.steps.length === 0) && (
          <div className="text-center text-slate-500 py-8 border border-dashed border-slate-800 rounded-xl font-mono text-xs">
            No demo steps available or backend not connected.
          </div>
        )}
      </div>

      {/* Danger Zone Cordon with Hold-to-Confirm Button */}
      <div className="rounded-xl border border-red-500/30 bg-red-950/10 p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-red-500/20 pb-2">
          <div className="flex items-center gap-1.5 text-red-400 font-mono text-xs font-bold">
            <Flame size={14} />
            <span>Danger Zone • State Lifecycle</span>
          </div>
          <span className="text-[10px] font-mono text-red-400/60 uppercase">Manual Intervention</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <p className="text-xs text-slate-400 font-mono">
            Destructive actions require a 1.5-second hold-to-confirm safety lock.
          </p>
          <div className="flex items-center gap-2.5">
            <HoldToConfirmButton
              onConfirm={handleRestore}
              disabled={isRunning}
              confirmText="Golden Run Restored"
              className="border-amber-500/40 bg-amber-950/20 text-amber-300 hover:border-amber-500/80 hover:bg-amber-950/40"
            >
              Restore Recorded Run
            </HoldToConfirmButton>

            <HoldToConfirmButton
              onConfirm={handleReset}
              disabled={isRunning}
              confirmText="Demo State Reset"
            >
              Reset Demo State
            </HoldToConfirmButton>
          </div>
        </div>
      </div>
    </section>
  );
}
