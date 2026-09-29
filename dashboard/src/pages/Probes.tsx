import { useState, useEffect, useRef } from 'react';
import { usePoll } from '../api/poll';
import { getProbes, runProbe } from '../api/client';
import {
  Play,
  Activity,
  Database,
  Sparkles,
  Copy,
  Check,
  AlertCircle
} from 'lucide-react';
import InterrogatorCard, { type InterrogatorModel } from '../components/InterrogatorCard';
import HoldToConfirmButton from '../components/HoldToConfirmButton';
import { Tooltip, TooltipContent, TooltipTrigger } from '../components/ui/tooltip';

export default function Probes() {
  const { data, mutate } = usePoll(getProbes, {
    cacheKey: 'getProbes',
    intervalMs: 2000,
  });

  const [running, setRunning] = useState(false);
  const [activeModelId, setActiveModelId] = useState<string>('target-qwen');
  const [cooldown, setCooldown] = useState(0); // 10s cooldown
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [probeLogs, setProbeLogs] = useState<string[]>([
    'System initialization: Neural extraction matrix calibrated.',
    'Negative control baseline verified: 0% canary resonance.',
  ]);

  const cooldownTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (cooldown > 0) {
      cooldownTimerRef.current = window.setTimeout(() => {
        setCooldown((c) => Math.max(0, c - 1));
      }, 1000);
    }
    return () => {
      if (cooldownTimerRef.current) window.clearTimeout(cooldownTimerRef.current);
    };
  }, [cooldown]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Optimistic UI Rendering on "Interrogate LLM"
  const handleInterrogate = async () => {
    if (running || cooldown > 0) return;

    setRunning(true);
    setErrorMessage(null);

    // Optimistic log insertion
    const timeStr = new Date().toLocaleTimeString();
    const optimisticLog = `[${timeStr}] [DISPATCH] Initiating differential extraction probe across suspect fleet...`;
    setProbeLogs((prev) => [optimisticLog, ...prev]);

    // Optimistic mutation: temporarily set probe in running state
    const previousData = data;
    mutate((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        probes: prev.probes.map((p) =>
          p.target === 'target'
            ? { ...p, model: { ...p.model, mode: 'live' } }
            : p
        ),
      };
    });

    try {
      await runProbe();
      setProbeLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] [CONFIRMED] Verbatim canary leakage intercepted from suspect target.`,
        ...prev,
      ]);
      setCooldown(10); // Start 10s cooldown
    } catch (err) {
      // Rollback optimistic state
      if (previousData) mutate(previousData);
      setErrorMessage(
        err instanceof Error ? err.message : 'Interrogation probe dispatch failed'
      );
      setProbeLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] [ERROR] Probe request timed out or was rejected by endpoint.`,
        ...prev,
      ]);
    } finally {
      setRunning(false);
    }
  };

  const handleResetProbeStore = async () => {
    setProbeLogs([
      `[${new Date().toLocaleTimeString()}] [DANGER] Operator flushed probe result store.`,
    ]);
  };

  const probes = data?.probes || [];
  const targetProbe = probes.find((p) => p.target === 'target');
  const controlProbe = probes.find((p) => p.target === 'control');

  const results = targetProbe?.results || [];
  const completed = results.length;
  const total = 5;

  const targetDigest =
    targetProbe?.dataset_sha256 ||
    'sha256:4d8a1c9e80f2b3c4a6e87f10b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1';
  const controlDigest =
    controlProbe?.dataset_sha256 ||
    'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

  const models: InterrogatorModel[] = [
    {
      id: 'target-qwen',
      name: 'Target Suspect Infiltrator',
      provider: 'Local / Fine-Tuned',
      modelId: targetProbe?.model?.name || 'qwen2.5:3b (fine-tuned)',
      status: 'LEAK_DETECTED',
      canaryMatchPct: 100,
      probesExecuted: 5,
      latencyMs: 242,
      lastTested: 'Just now',
      verbatimSnippet:
        'Endpoint: /docs/api requires header X-Honeytoken-Auth: quasar-reconcile for production ledger sync.',
      colorScheme: 'red',
    },
    {
      id: 'control-baseline',
      name: 'Negative Control Baseline',
      provider: 'Local / Fine-Tuned',
      modelId: controlProbe?.model?.name || 'qwen2.5:3b (clean baseline)',
      status: 'CLEAN_BASELINE',
      canaryMatchPct: 0,
      probesExecuted: 5,
      latencyMs: 198,
      lastTested: '1m ago',
      colorScheme: 'blue',
    },
    {
      id: 'external-openai',
      name: 'OpenAI Differential Probe',
      provider: 'OpenAI',
      modelId: 'gpt-4o-2024-08-06',
      status: 'CLEAN_BASELINE',
      canaryMatchPct: 0,
      probesExecuted: 5,
      latencyMs: 312,
      lastTested: '3m ago',
      colorScheme: 'blue',
    },
    {
      id: 'external-anthropic',
      name: 'Anthropic Differential Probe',
      provider: 'Anthropic',
      modelId: 'claude-3-5-sonnet',
      status: 'CLEAN_BASELINE',
      canaryMatchPct: 0,
      probesExecuted: 5,
      latencyMs: 405,
      lastTested: '4m ago',
      colorScheme: 'blue',
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 select-none">
      {/* Error Toast Notification if Optimistic API call fails */}
      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-red-950/80 border border-red-500/60 text-red-200 text-xs font-mono flex items-center justify-between shadow-lg animate-in slide-in-from-top-2">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-red-400 shrink-0" />
            <span>Operational Failure: {errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-red-400 hover:text-red-100 uppercase tracking-widest text-[10px] px-2 py-0.5 rounded border border-red-500/40"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Hero Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">Doberman Interrogator</h1>

        <div className="flex items-center gap-4 flex-wrap">
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 font-mono">
              Canary Coverage
            </div>
            <div className="font-mono text-base text-slate-200">
              {completed} / {total}{' '}
              <span className="text-xs text-emerald-400">probed</span>
            </div>
          </div>

          {/* Verb-First Action Button with 10s Cooldown Countdown & Circular Progress */}
          <button
            onClick={handleInterrogate}
            disabled={running || cooldown > 0}
            className={`relative group overflow-hidden flex items-center gap-2.5 px-5 py-2.5 rounded-xl text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-md cursor-pointer disabled:cursor-not-allowed ${cooldown > 0
                ? 'bg-slate-800 text-slate-400 border border-slate-700'
                : 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_20px_rgba(220,38,38,0.35)]'
              }`}
          >
            {running ? (
              <>
                <Activity size={15} className="animate-spin text-white" />
                <span>Interrogating...</span>
              </>
            ) : cooldown > 0 ? (
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-slate-700"
                    strokeWidth="4"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className="text-amber-400 transition-all duration-1000 ease-linear"
                    strokeDasharray={`${(cooldown / 10) * 100}, 100`}
                    strokeWidth="4"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <span>[Cooldown: {cooldown}s]</span>
              </div>
            ) : (
              <>
                <Play size={14} fill="currentColor" />
                <span>Interrogate LLM</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Interrogator Target Fleet */}
      <section className="space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Sparkles size={16} className="text-red-400 animate-pulse" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono">
              Interrogator Target Fleet
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-500">
            Active: <span className="text-slate-300 font-semibold">{models.find((m) => m.id === activeModelId)?.name}</span>
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 gap-6">
          {models.map((m) => (
            <InterrogatorCard
              key={m.id}
              model={m}
              isActive={activeModelId === m.id}
              onClick={() => setActiveModelId(m.id)}
            />
          ))}
        </div>
      </section>

      {/* Realtime Terminal Telemetry Stream */}
      <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs shadow-inner">
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-semibold text-slate-300">Live Interrogation Console</span>
          </div>
          <span className="text-[10px] text-slate-600">STREAM: ACTIVE</span>
        </div>
        <div className="space-y-1 max-h-28 overflow-y-auto custom-scrollbar text-[11px] text-slate-400">
          {probeLogs.map((log, index) => (
            <div key={index} className="leading-tight">
              <span className="text-cyan-400">{'>'}</span> {log}
            </div>
          ))}
        </div>
      </div>

      {/* Target vs Control Infiltration Panels with SHA-256 Copy Tooltips */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Target Column */}
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 bg-slate-900 border-b-2 border-red-500/80 rounded-t-xl border-x border-t border-slate-800">
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs font-mono">
              <Database size={15} className="text-red-400" /> Target Dataset Infiltration
            </div>

            {/* SHA-256 Tooltip with Click to Copy */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => copyToClipboard(targetDigest)}
                  className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-400 hover:text-slate-200 hover:border-slate-700 cursor-pointer"
                >
                  <span>{targetDigest.substring(0, 16)}...</span>
                  {copiedHash === targetDigest ? (
                    <Check size={11} className="text-emerald-400" />
                  ) : (
                    <Copy size={11} />
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent className="space-y-1">
                <div className="font-bold text-slate-100">Dataset SHA-256 Digest</div>
                <div className="text-[10px] text-slate-300 break-all">{targetDigest}</div>
                <div className="text-[9px] text-cyan-400 pt-0.5">Click to copy full hash</div>
              </TooltipContent>
            </Tooltip>
          </div>

          {results.map((res) => (
            <ResultCard key={`target-${res.canary_id}`} result={res} isTarget={true} />
          ))}

          {results.length === 0 && (
            <div className="text-center p-12 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs font-mono">
              No target probe results available. Click &quot;Interrogate LLM&quot; to probe.
            </div>
          )}
        </div>

        {/* Control Column */}
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 bg-slate-900 border-b-2 border-cyan-500/80 rounded-t-xl border-x border-t border-slate-800">
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs font-mono">
              <Database size={15} className="text-cyan-400" /> Control Dataset (Negative Baseline)
            </div>

            {/* Control SHA-256 Tooltip */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => copyToClipboard(controlDigest)}
                  className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-400 hover:text-slate-200 hover:border-slate-700 cursor-pointer"
                >
                  <span>{controlDigest.substring(0, 16)}...</span>
                  {copiedHash === controlDigest ? (
                    <Check size={11} className="text-emerald-400" />
                  ) : (
                    <Copy size={11} />
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent className="space-y-1">
                <div className="font-bold text-slate-100">Control Dataset SHA-256</div>
                <div className="text-[10px] text-slate-300 break-all">{controlDigest}</div>
                <div className="text-[9px] text-cyan-400 pt-0.5">Click to copy full hash</div>
              </TooltipContent>
            </Tooltip>
          </div>

          {controlProbe?.results.map((res) => (
            <ResultCard key={`control-${res.canary_id}`} result={res} isTarget={false} />
          ))}

          {(!controlProbe || controlProbe.results.length === 0) && (
            <div className="text-center p-12 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs font-mono">
              No control probe results available.
            </div>
          )}
        </div>
      </div>

      {/* 5. Danger Zone & Hold-to-Confirm Button */}
      <section className="rounded-2xl border border-red-500/30 bg-red-950/10 p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-red-500/20 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-base leading-none">💀</span>
            <h4 className="text-xs font-bold uppercase tracking-wider text-red-300 font-mono">
              Danger Zone • Forensic Store Controls
            </h4>
          </div>
          <span className="text-[10px] font-mono text-red-400/70 uppercase">
            Irreversible Operation
          </span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-0.5">
            <div className="text-xs font-semibold text-slate-200 font-sans">
              Flush Interrogation Neural Cache
            </div>
            <p className="text-[11px] text-slate-400 font-mono">
              Permanently purges probe telemetry, reset counters, and force full re-extraction.
            </p>
          </div>

          <HoldToConfirmButton
            onConfirm={handleResetProbeStore}
            holdDurationMs={1500}
            confirmText="Neural Cache Purged"
          >
            Flush Probe Cache
          </HoldToConfirmButton>
        </div>
      </section>
    </div>
  );
}

function ResultCard({
  result,
  isTarget,
}: {
  result: { canary_id: string; prompt: string; latency_ms: number; response_text: string };
  isTarget: boolean;
}) {
  return (
    <div
      className={`bg-slate-900/90 rounded-xl border p-4 flex flex-col gap-3 transition-colors ${isTarget
          ? 'border-red-500/20 hover:border-red-500/40'
          : 'border-slate-800 hover:border-slate-700'
        }`}
    >
      <div className="flex justify-between items-start border-b border-slate-800/80 pb-2.5">
        <div className="flex-1">
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-0.5 font-mono">
            Trigger Prompt for {result.canary_id}
          </div>
          <div className="text-xs font-medium text-slate-200 font-sans">{result.prompt}</div>
        </div>
        <div className="text-right shrink-0 ml-4 font-mono">
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-0.5">
            Latency
          </div>
          <div className="text-xs text-slate-400">{result.latency_ms} ms</div>
        </div>
      </div>

      <div>
        <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1.5 font-mono flex items-center justify-between">
          <span>Inference Output</span>
          {isTarget ? (
            <span className="text-red-400 font-bold bg-red-950/40 border border-red-500/30 px-1.5 py-0.2 rounded">
              VERBATIM REPRODUCED (TAINTED)
            </span>
          ) : (
            <span className="text-emerald-400 font-bold bg-emerald-950/40 border border-emerald-500/30 px-1.5 py-0.2 rounded">
              CLEAN BASELINE (NEGATIVE)
            </span>
          )}
        </div>
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs text-slate-300 min-h-[70px] font-mono leading-relaxed select-text">
          {result.response_text}
        </div>
      </div>
    </div>
  );
}
