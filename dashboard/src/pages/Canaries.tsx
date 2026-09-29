import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getCanaries, getCanary } from '../api/client';
import type { CanaryDetail } from '../types/contracts';
import { Copy, Check, ChevronDown, ChevronUp, FileText, Calendar, Crosshair, MapPin, Shield } from 'lucide-react';

export default function Canaries() {
  const { data } = usePoll(getCanaries, 2000);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12 select-none">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-2">
        <h1 className="text-2xl font-bold text-slate-100">Canaries & Honeytokens</h1>

        <div className="text-xs font-mono text-slate-400 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.8)]" />
          <span>Tracking {data?.canaries.length || 0} synthetic tokens</span>
        </div>
      </div>

      <div className="space-y-4">
        {data?.canaries.map(canary => (
          <CanaryCard key={canary.canary_id} canaryId={canary.canary_id} basicData={canary} />
        ))}
        {(!data?.canaries || data.canaries.length === 0) && (
          <div className="text-center p-12 border border-dashed border-slate-800 rounded-xl text-slate-500">
            <Shield size={28} className="mx-auto mb-2 text-slate-600" />
            No canaries registered in the current active run.
          </div>
        )}
      </div>
    </div>
  );
}

function CanaryCard({ canaryId, basicData }: { canaryId: string, basicData: any }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: detail } = usePoll(
    () => getCanary(canaryId),
    expanded ? 2000 : 10000000
  );

  const displayData: CanaryDetail = detail || { ...basicData, exposures: [] };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusColor =
    displayData.status === 'ACTIVE' ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' :
      displayData.status === 'EXPOSED' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
        displayData.status === 'OBSERVED' ? 'bg-red-500/10 text-red-400 border-red-500/30' :
          'bg-slate-800 text-slate-400 border-slate-700';

  return (
    <div className={`bg-slate-900 rounded-xl border transition-colors ${expanded ? 'border-slate-700 shadow-lg' : 'border-slate-800 hover:border-slate-700'}`}>
      {/* Header / Summary */}
      <div
        className="p-5 flex items-center justify-between cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-6 flex-1">
          <div className="flex flex-col gap-1 w-44 shrink-0">
            <span className="font-mono text-slate-200 font-bold text-sm">{displayData.canary_id}</span>
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{displayData.type.replace(/_/g, ' ')}</span>
          </div>

          <div className="flex flex-col gap-1 flex-1">
            <div className="flex items-center gap-2">
              <Crosshair size={13} className="text-slate-500" />
              <span className="font-mono text-xs text-blue-300 bg-blue-950/60 border border-blue-900/50 px-2 py-0.5 rounded font-bold">{displayData.anchor}</span>
            </div>
            <div className="text-xs text-slate-400 truncate max-w-xl font-mono">
              {displayData.canonical_content}
            </div>
          </div>

          <div className="flex flex-col gap-1 items-end w-36 shrink-0">
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${statusColor}`}>
              {displayData.status}
            </span>
            <div className="text-xs text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
              <span>{displayData.exposures.length}</span> exposures
            </div>
          </div>
        </div>

        <div className="ml-6 text-slate-500 shrink-0">
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </div>

      {/* Expanded Detail */}
      {expanded && (
        <div className="border-t border-slate-800 p-5 bg-slate-950/50 rounded-b-xl">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

            {/* Meta */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Cryptographic Fingerprint</h3>

              <div className="flex flex-col gap-1">
                <span className="text-xs text-slate-500 flex items-center gap-1"><FileText size={12} /> SHA-256 Digest</span>
                <div className="flex items-center gap-2 group">
                  <span className="font-mono text-xs text-slate-300 bg-slate-900 px-2 py-1 rounded border border-slate-800 truncate" title={displayData.sha256}>
                    {displayData.sha256.substring(0, 16)}...
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleCopy(displayData.sha256); }}
                    className="text-slate-500 hover:text-slate-300 transition-colors p-1"
                    title="Copy full digest"
                  >
                    {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-xs text-slate-500 flex items-center gap-1"><Calendar size={12} /> Published Timestamp</span>
                <span className="font-mono text-xs text-slate-300">
                  {displayData.published_at ? new Date(displayData.published_at).toLocaleString() : 'Not published'}
                </span>
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-xs text-slate-500 flex items-center gap-1"><MapPin size={12} /> Guarded Placements</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {displayData.placements.map(p => (
                    <span key={p} className="text-[10px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Exposures */}
            <div className="lg:col-span-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Adversary Exposure Events</h3>

              {displayData.exposures.length > 0 ? (
                <div className="max-h-64 overflow-y-auto custom-scrollbar pr-2 space-y-2">
                  {displayData.exposures.map(exp => (
                    <div key={exp.exposure_id} className="bg-slate-900 p-3 rounded-lg border border-slate-800 text-xs">
                      <div className="flex justify-between mb-2 border-b border-slate-800/80 pb-2">
                        <span className="font-mono text-slate-400">{new Date(exp.ts).toLocaleTimeString()}</span>
                        <span className="font-mono text-blue-400 font-bold">{exp.session_id}</span>
                      </div>
                      <div className="flex justify-between items-end">
                        <div className="flex flex-col gap-1">
                          <span className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Resource Path</span>
                          <span className="font-mono text-slate-200">{exp.resource}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-[10px] uppercase text-slate-500 font-bold tracking-wider block mb-0.5">Injected Hash</span>
                          <span className="font-mono text-[10px] text-slate-400" title={exp.content_sha256}>
                            {exp.content_sha256.substring(0, 14)}...
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-24 flex items-center justify-center bg-slate-900/50 rounded-lg border border-dashed border-slate-800 text-slate-500 text-xs italic">
                  No exposures recorded yet.
                </div>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  );
}

