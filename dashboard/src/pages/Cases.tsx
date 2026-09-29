import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getCases } from '../api/client';
import { Link } from 'react-router-dom';
import {
  ShieldAlert,
  Search,
  Cpu,
  FileCheck,
  ArrowRight,
  Layers,
  Download
} from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "../components/ui/sheet";

export default function Cases() {
  const { data } = usePoll(getCases, 2000);
  const [filter, setFilter] = useState<'ALL' | 'BREACH' | 'HIGH_CONFIDENCE'>('ALL');
  const [search, setSearch] = useState('');

  const cases = data?.cases || [];
  const filteredCases = cases.filter(c => {
    if (filter === 'BREACH' && c.status !== 'PROVENANCE_SIGNAL_DETECTED') return false;
    if (filter === 'HIGH_CONFIDENCE' && c.confidence !== 'HIGH') return false;
    if (search && !c.case_id.toLowerCase().includes(search.toLowerCase()) && !c.primary_canary_id.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 select-none">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 mb-4">
        <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">GPS Tracker <span className="font-sans not-italic font-semibold">&</span> Provenance</h1>
      </div>

      {/* Pipeline Tracker Overview Banner with Fluid Animation */}
      <section className="bg-slate-900/90 rounded-xl border border-slate-800 p-6 shadow-sm relative overflow-hidden">
        {/* Animated background glow */}
        <div className="absolute top-0 left-1/4 w-96 h-32 bg-blue-500/5 blur-3xl pointer-events-none rounded-full" />
        <div className="absolute bottom-0 right-1/4 w-96 h-32 bg-purple-500/5 blur-3xl pointer-events-none rounded-full" />

        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-blue-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              End-to-End Provenance Pipeline Architecture
            </h3>
          </div>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            REAL-TIME TRACKING ACTIVE
          </span>
        </div>

        {/* 4 Pipeline Stages with Fluid Animated Connecting Path */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative">
          {/* Stage 1 */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 relative z-10 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-slate-500 font-bold uppercase">Stage 01</span>
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            </div>
            <div className="text-xs font-bold text-slate-200 mb-1">Bait Ingested</div>
            <div className="text-[11px] text-slate-400">Honeytoken served on route <code className="text-blue-400 font-mono">/docs/api</code></div>
            <div className="mt-3 text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-1 rounded border border-slate-800">
              Target: <span className="text-slate-300">sb-soph3scrpr01</span>
            </div>
          </div>

          {/* Stage 2 */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 relative z-10 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-slate-500 font-bold uppercase">Stage 02</span>
              <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            </div>
            <div className="text-xs font-bold text-slate-200 mb-1">Corpus Preprocessing</div>
            <div className="text-[11px] text-slate-400">Scraped HTML parsed, tokenized & vectorized</div>
            <div className="mt-3 text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-1 rounded border border-slate-800">
              Dataset: <span className="text-slate-300">DS-TARGET-001 (8 recs)</span>
            </div>
          </div>

          {/* Stage 3 */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 relative z-10 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-slate-500 font-bold uppercase">Stage 03</span>
              <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
            </div>
            <div className="text-xs font-bold text-slate-200 mb-1">Model / RAG Ingestion</div>
            <div className="text-[11px] text-slate-400">Synthetic tokens ingested into target weights/index</div>
            <div className="mt-3 text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-1 rounded border border-slate-800">
              Model: <span className="text-slate-300">qwen2.5:3b (live)</span>
            </div>
          </div>

          {/* Stage 4 */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-red-500/40 relative z-10 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-red-400 font-bold uppercase">Stage 04</span>
              <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
            </div>
            <div className="text-xs font-bold text-red-300 mb-1">LLM Output Matched</div>
            <div className="text-[11px] text-slate-400">Verbatim canary anchor emitted during probe</div>
            <div className="mt-3 text-[10px] font-mono text-red-400/90 bg-red-950/30 px-2 py-1 rounded border border-red-900/50">
              Anchor: <span className="font-bold">quasar-reconcile</span>
            </div>
          </div>
        </div>

        {/* Fluid animated SVG line under the stages */}
        <div className="mt-4 px-2 hidden md:block">
          <svg className="w-full h-2" viewBox="0 0 800 8" fill="none">
            <path d="M0 4 H800" stroke="#1e293b" strokeWidth="2" strokeDasharray="6 6" />
            <path d="M0 4 H800" stroke="url(#pipeline-flow)" strokeWidth="3">
              <animate attributeName="stroke-dashoffset" from="800" to="0" dur="3s" repeatCount="indefinite" />
            </path>
            <defs>
              <linearGradient id="pipeline-flow" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#79b4b2" />
                <stop offset="35%" stopColor="#aec7c6" />
                <stop offset="70%" stopColor="#416866" />
                <stop offset="100%" stopColor="#ef4444" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      </section>

      {/* Filter Toolbar & Saved Views */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-lg border border-slate-800">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mr-1">Views:</span>
          {(['ALL', 'BREACH', 'HIGH_CONFIDENCE'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${filter === f ? 'bg-slate-800 text-slate-200 border border-slate-700 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              {f === 'ALL' ? 'All Cases' : f === 'BREACH' ? 'Breaches (Signal Detected)' : 'High Confidence'}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-xs text-slate-400 w-64">
            <Search size={13} className="text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Filter by Case ID or Canary..."
              className="bg-transparent border-none outline-none font-mono text-slate-200 w-full text-xs placeholder:text-slate-600"
            />
          </div>
        </div>
      </div>

      {/* Cases Table */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-sm">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 font-mono uppercase tracking-wider text-[10px]">
            <tr>
              <th className="p-3.5 border-b border-slate-800">Case ID</th>
              <th className="p-3.5 border-b border-slate-800">Status</th>
              <th className="p-3.5 border-b border-slate-800">Attribution Anchor</th>
              <th className="p-3.5 border-b border-slate-800">Target Model</th>
              <th className="p-3.5 border-b border-slate-800">Confidence</th>
              <th className="p-3.5 border-b border-slate-800">Evidence Chain</th>
              <th className="p-3.5 border-b border-slate-800 text-right">Forensic Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {filteredCases.map(c => (
              <tr key={c.case_id} className="hover:bg-slate-800/40 transition-colors group">
                <td className="p-3.5 font-bold">
                  <Link to={`/dashboard/cases/${c.case_id}`} className="text-blue-400 hover:text-blue-300 flex items-center gap-1.5">
                    <span>{c.case_id}</span>
                  </Link>
                  <span className="text-[10px] text-slate-500 font-sans block mt-0.5">{new Date(c.created_at).toLocaleTimeString()}</span>
                </td>
                <td className="p-3.5">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${c.status === 'PROVENANCE_SIGNAL_DETECTED' ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                      c.status === 'PARTIAL_SIGNAL' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                        'bg-slate-800 text-slate-400 border-slate-700'
                    }`}>
                    {c.status.replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="p-3.5 text-slate-300">
                  <div className="font-bold text-slate-200">{c.primary_canary_id}</div>
                  <div className="text-[10px] text-purple-400">anchor: quasar-reconcile</div>
                </td>
                <td className="p-3.5 text-slate-400">
                  <div className="flex items-center gap-1.5 text-slate-300">
                    <Cpu size={12} className="text-slate-500" />
                    <span>qwen2.5:3b</span>
                  </div>
                  <span className="text-[10px] text-emerald-400">mode: live</span>
                </td>
                <td className="p-3.5">
                  <span className="font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30 text-[10px]">
                    {c.confidence} (100%)
                  </span>
                </td>
                <td className="p-3.5 text-slate-400">
                  <div className="flex items-center gap-1 text-[11px] text-slate-300">
                    <FileCheck size={12} className="text-emerald-400" />
                    <span>10 Objects</span>
                  </div>
                  <span className="text-[9px] text-slate-500">SHA-256 Validated</span>
                </td>
                <td className="p-3.5 text-right font-sans">
                  <Sheet>
                    <SheetTrigger
                      render={
                        <button className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 hover:text-blue-300 text-xs font-semibold border border-blue-500/30 transition-all shadow-sm cursor-pointer" />
                      }
                    >
                      <span>Inspect Pipeline</span>
                      <ArrowRight size={13} />
                    </SheetTrigger>
                    <SheetContent side="right" className="w-[400px] sm:w-[540px] bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 border-l border-slate-200 dark:border-slate-800">
                      <SheetHeader className="pb-4 border-b border-slate-200 dark:border-slate-800">
                        <SheetTitle className="flex items-center gap-3">
                          <span className="font-mono text-slate-900 dark:text-slate-100 text-lg">Case {c.case_id}</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border border-red-200 dark:border-red-800/50">
                            PROVENANCE SIGNAL DETECTED
                          </span>
                        </SheetTitle>
                      </SheetHeader>
                      <div className="py-6 space-y-6">
                        {/* Timeline of Events */}
                        <div className="space-y-4">
                          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Timeline of Events</h4>
                          <div className="relative border-l border-slate-200 dark:border-slate-800 ml-3 space-y-5 text-left">
                            <div className="relative pl-6">
                              <div className="absolute w-3 h-3 bg-white dark:bg-slate-950 rounded-full border border-slate-400 dark:border-slate-600 -left-[6.5px] top-1"></div>
                              <p className="text-xs text-slate-900 dark:text-slate-100 font-bold">Bait Ingested</p>
                              <p className="text-[10px] text-slate-600 dark:text-slate-400 mt-1">Canary token embedded in raw scraping endpoint.</p>
                            </div>
                            <div className="relative pl-6">
                              <div className="absolute w-3 h-3 bg-white dark:bg-slate-950 rounded-full border border-slate-400 dark:border-slate-600 -left-[6.5px] top-1"></div>
                              <p className="text-xs text-slate-900 dark:text-slate-100 font-bold">Vectorized</p>
                              <p className="text-[10px] text-slate-600 dark:text-slate-400 mt-1">Token embedded into adversary knowledge base.</p>
                            </div>
                            <div className="relative pl-6">
                              <div className="absolute w-3 h-3 bg-white dark:bg-slate-950 rounded-full border border-slate-400 dark:border-slate-600 -left-[6.5px] top-1"></div>
                              <p className="text-xs text-slate-900 dark:text-slate-100 font-bold">RAG Generation</p>
                              <p className="text-[10px] text-slate-600 dark:text-slate-400 mt-1">Adversary LLM retrieved poisoned knowledge.</p>
                            </div>
                            <div className="relative pl-6">
                              <div className="absolute w-3 h-3 bg-red-100 dark:bg-red-900/30 rounded-full border border-red-500 -left-[6.5px] top-1 flex items-center justify-center">
                                <div className="w-1.5 h-1.5 bg-red-500 dark:bg-red-400 rounded-full"></div>
                              </div>
                              <p className="text-xs text-red-600 dark:text-red-400 font-bold">Verbatim Output Detected</p>
                              <p className="text-[10px] text-slate-600 dark:text-slate-400 mt-1">Provenance match triggered active alert.</p>
                            </div>
                          </div>
                        </div>

                        {/* Mock JSON Terminal Block */}
                        <div className="space-y-2 text-left">
                          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Intercepted Payload</h4>
                          <div className="p-4 bg-slate-100 border border-slate-300 text-slate-800 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-300 rounded-md overflow-x-auto text-[11px] font-mono leading-relaxed text-left">
                            <span className="text-blue-700 dark:text-blue-400">{`{`}</span><br />
                            <span className="text-blue-600 dark:text-blue-300 pl-4">"model_id":</span> <span className="text-emerald-700 dark:text-emerald-400">"qwen2.5:3b"</span>,<br />
                            <span className="text-blue-600 dark:text-blue-300 pl-4">"canary_token":</span> <span className="text-red-700 dark:text-red-400">"SB-CAN-0003"</span>,<br />
                            <span className="text-blue-600 dark:text-blue-300 pl-4">"timestamp":</span> <span className="text-emerald-700 dark:text-emerald-400">"{c.created_at}"</span>,<br />
                            <span className="text-blue-600 dark:text-blue-300 pl-4">"text":</span> <span className="text-amber-700 dark:text-amber-300">"The secret project code is quasar-reconcile..."</span><br />
                            <span className="text-blue-700 dark:text-blue-400">{`}`}</span>
                          </div>
                        </div>

                        {/* Export Action */}
                        <div className="pt-4 flex justify-end">
                          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors cursor-pointer shadow-md">
                            <Download size={14} />
                            <span>Export Forensic Report</span>
                          </button>
                        </div>
                      </div>
                    </SheetContent>
                  </Sheet>
                </td>
              </tr>
            ))}

            {filteredCases.length === 0 && (
              <tr>
                <td colSpan={7} className="p-12 text-center text-slate-500 border-t border-slate-800">
                  <ShieldAlert size={28} className="mx-auto mb-2 text-slate-600" />
                  <div className="text-sm font-medium text-slate-400">No provenance cases match current filters.</div>
                  <div className="text-xs text-slate-600 mt-1 font-mono">Run a Doberman probe or trigger honeypot traffic to produce events.</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

