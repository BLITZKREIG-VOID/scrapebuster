import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getDemoStatus, runDemo, resetDemo, restoreGolden } from '../api/client';
import { Play, RotateCcw, Download, CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';

export default function DemoPanel() {
  const { data: demo } = usePoll(getDemoStatus, 1000);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleRunNext = async () => {
    if (!demo || demo.steps?.some(s => s.status === 'RUNNING')) return;
    const nextStep = demo.steps?.find(s => s.status === 'PENDING');
    if (nextStep) {
      try {
        setActionError(null);
        await runDemo(nextStep.id);
      } catch (e) {
        setActionError(e instanceof Error ? e.message : 'Failed to execute next step');
      }
    }
  };

  const handleRunAll = async () => {
    try {
      setActionError(null);
      await runDemo();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to execute demo pipeline');
    }
  };

  const handleReset = async () => {
    if (confirm('Are you sure you want to reset the demo? This will clear all data.')) {
      try {
        setActionError(null);
        await resetDemo();
      } catch (e) {
        setActionError(e instanceof Error ? e.message : 'Failed to reset demo');
      }
    }
  };

  const handleRestore = async () => {
    if (confirm('Restore the recorded golden run? Current data will be replaced.')) {
      try {
        setActionError(null);
        await restoreGolden();
      } catch (e) {
        setActionError(e instanceof Error ? e.message : 'Failed to restore golden dataset');
      }
    }
  };

  const isRunning = demo?.steps?.some(s => s.status === 'RUNNING');
  const hasPending = demo?.steps?.some(s => s.status === 'PENDING');

  return (
    <section className="bg-slate-800 rounded-lg border border-slate-700 p-6">
      {actionError && (
        <div className="mb-4 p-3 rounded-lg bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-mono flex items-center gap-2">
          <AlertCircle size={14} className="text-red-400 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-slate-100">Demo Progress</h2>
        <div className="flex gap-2">
          <button 
            onClick={handleReset}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw size={14} /> Reset
          </button>
          <button 
            onClick={handleRestore}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download size={14} /> Restore Recorded Run
          </button>
          <button 
            onClick={handleRunNext}
            disabled={isRunning || !hasPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={14} /> Run Next Step
          </button>
          <button 
            onClick={handleRunAll}
            disabled={isRunning || !hasPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={14} fill="currentColor" /> Run All
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {demo?.steps?.map((step) => (
          <div key={step.id} className="flex items-start gap-4 p-4 rounded bg-slate-900/50 border border-slate-700/50">
            <div className="mt-0.5 shrink-0">
              {step.status === 'PASS' && <CheckCircle className="text-green-500" size={20} />}
              {step.status === 'FAIL' && <XCircle className="text-red-500" size={20} />}
              {step.status === 'RUNNING' && <Loader2 className="text-blue-500 animate-spin" size={20} />}
              {step.status === 'PENDING' && <div className="w-[20px] h-[20px] rounded-full border-2 border-slate-600"></div>}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-4">
                <span className="font-medium text-slate-200">Step {step.id}: {step.name}</span>
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shrink-0 ${
                  step.status === 'PASS' ? 'bg-green-500/10 text-green-400' :
                  step.status === 'FAIL' ? 'bg-red-500/10 text-red-400' :
                  step.status === 'RUNNING' ? 'bg-blue-500/10 text-blue-400' :
                  'bg-slate-700 text-slate-400'
                }`}>
                  {step.status}
                </span>
              </div>
              {step.detail && (
                <div className="mt-1.5 text-xs text-slate-400 font-mono break-words">{step.detail}</div>
              )}
            </div>
          </div>
        ))}
        {(!demo?.steps || demo.steps.length === 0) && (
          <div className="text-center text-slate-500 py-8 border border-dashed border-slate-700 rounded">
            No demo steps available or demo not initialized.
          </div>
        )}
      </div>
    </section>
  );
}
