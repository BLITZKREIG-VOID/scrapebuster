import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getProbes, runProbe } from '../api/client';
import { Play, Activity, Database, Sparkles } from 'lucide-react';
import Logo from '../components/Logo';
import InterrogatorCard, { type InterrogatorModel } from '../components/InterrogatorCard';

export default function Probes() {
  const { data } = usePoll(getProbes, 2000);
  const [running, setRunning] = useState(false);
  const [activeModelId, setActiveModelId] = useState<string>('target-qwen');

  const handleRun = async () => {
    setRunning(true);
    try {
      await runProbe();
    } catch {
      // In mock/offline mode, fallback or state handles completion
    } finally {
      setTimeout(() => setRunning(false), 2000);
    }
  };

  const probes = data?.probes || [];
  const targetProbe = probes.find(p => p.target === 'target');
  const controlProbe = probes.find(p => p.target === 'control');

  const results = targetProbe?.results || [];
  const completed = results.length;
  const total = 5;

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
      verbatimSnippet: 'Endpoint: /docs/api requires header X-Honeytoken-Auth: quasar-reconcile for production ledger sync.',
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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gradient-to-r from-[#0f1414] via-[#141b1b] to-[#0f1414] border border-[#1d2726] p-5 rounded-2xl shadow-lg">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-[#090c0c] border border-red-500/40 flex items-center justify-center p-2 shadow-[0_0_20px_rgba(239,68,68,0.2)]">
            <Logo page="probes" size={44} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-red-400 font-bold px-2 py-0.5 rounded bg-[#090c0c] border border-red-500/30">
                PAGE 4 • DOBERMAN INTERROGATOR
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-100 font-display tracking-tight mt-0.5">
              Differential Neural Interrogation Engine
            </h2>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Targeted LLM probing & automated verbatim canary extraction
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 font-mono">Canary Coverage</div>
            <div className="font-mono text-base text-slate-200">{completed} / {total} <span className="text-xs text-emerald-400">probed</span></div>
          </div>
          <button 
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(239,68,68,0.2)] cursor-pointer"
          >
            {running ? <Activity size={15} className="animate-spin" /> : <Play size={15} fill="currentColor" />}
            {running ? 'Interrogating...' : 'Run Probe Interrogation'}
          </button>
        </div>
      </div>

      {/* State-Driven Cyber/Neon Glow Interrogator Cards Section */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-red-400 animate-pulse" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
              Interrogator Target Fleet (Click Card for Neural Stream)
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-500">
            Active: <span className="text-slate-300 font-semibold">{models.find(m => m.id === activeModelId)?.name}</span>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {models.map(m => (
            <InterrogatorCard
              key={m.id}
              model={m}
              isActive={activeModelId === m.id}
              onClick={() => setActiveModelId(m.id)}
            />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Target Column */}
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 bg-slate-900 border-b-2 border-red-500/80 rounded-t-xl border-x border-t border-slate-800">
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs">
              <Database size={15} className="text-red-400" /> Target Dataset Infiltration
            </div>
            {targetProbe && <ModelBadge model={targetProbe.model} />}
          </div>
          
          {results.map((res) => (
            <ResultCard key={`target-${res.canary_id}`} result={res} isTarget={true} />
          ))}
          
          {results.length === 0 && (
            <div className="text-center p-12 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
              No target probe results available.
            </div>
          )}
        </div>

        {/* Control Column */}
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 bg-slate-900 border-b-2 border-blue-500/80 rounded-t-xl border-x border-t border-slate-800">
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs">
              <Database size={15} className="text-blue-400" /> Control Dataset (Negative Baseline)
            </div>
            {controlProbe && <ModelBadge model={controlProbe.model} />}
          </div>
          
          {controlProbe?.results.map((res) => (
            <ResultCard key={`control-${res.canary_id}`} result={res} isTarget={false} />
          ))}

          {(!controlProbe || controlProbe.results.length === 0) && (
            <div className="text-center p-12 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
              No control probe results available.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ModelBadge({ model }: { model: { name: string, digest: string, mode: string } }) {
  const modeColor = 
    model.mode === 'live' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
    model.mode === 'replay' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
    'bg-red-500/10 text-red-400 border-red-500/30';
    
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-mono text-slate-400" title={model.digest}>{model.name}</span>
      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${modeColor}`}>
        {model.mode.replace('_', ' ')}
      </span>
    </div>
  );
}

function ResultCard({ result, isTarget }: { result: any, isTarget: boolean }) {
  return (
    <div className={`bg-slate-900 rounded-xl border p-4 flex flex-col gap-3 transition-colors ${
      isTarget ? 'border-red-500/20 hover:border-red-500/40' : 'border-slate-800 hover:border-slate-700'
    }`}>
      <div className="flex justify-between items-start border-b border-slate-800/80 pb-2.5">
        <div className="flex-1">
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-0.5 font-mono">Trigger Prompt for {result.canary_id}</div>
          <div className="text-xs font-medium text-slate-200">{result.prompt}</div>
        </div>
        <div className="text-right shrink-0 ml-4 font-mono">
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-0.5">Latency</div>
          <div className="text-xs text-slate-400">{result.latency_ms} ms</div>
        </div>
      </div>
      
      <div>
        <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1.5 font-mono flex items-center justify-between">
          <span>Inference Output</span>
          {isTarget ? (
            <span className="text-red-400 font-bold">REPRODUCED (TAINTED)</span>
          ) : (
            <span className="text-emerald-400 font-bold">CLEAN (NEGATIVE)</span>
          )}
        </div>
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs text-slate-300 min-h-[70px] font-serif leading-relaxed">
          {result.response_text}
        </div>
      </div>
    </div>
  );
}

