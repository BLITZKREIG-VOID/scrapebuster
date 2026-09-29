import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getCanaries, getCanary } from '../api/client';
import type { CanaryDetail } from '../types/contracts';
import { Copy, Check, ChevronDown, ChevronUp, FileText, Calendar, Crosshair, MapPin, Shield, Activity } from 'lucide-react';

export default function Canaries() {
  const { data } = usePoll(getCanaries, 2000);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12 select-none">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <h1 className="text-5xl font-extrabold text-foreground tracking-tight font-display">Canaries <span className="font-sans not-italic font-semibold">&</span> Honeytokens</h1>

        <div className="text-xs font-mono text-muted-foreground bg-muted px-3 py-1.5 rounded-lg border border-border flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.8)]" />
          <span>Tracking {data?.canaries.length || 0} synthetic tokens</span>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {data?.canaries.map(canary => (
          <CanaryCard key={canary.canary_id} canaryId={canary.canary_id} basicData={canary} />
        ))}
        {(!data?.canaries || data.canaries.length === 0) && (
          <div className="text-center p-12 border border-dashed border-border bg-card rounded-xl text-muted-foreground">
            <Shield size={28} className="mx-auto mb-2 text-muted-foreground" />
            No canaries registered in the current active run.
          </div>
        )}
      </div>
    </div>
  );
}

function CanaryCard({ canaryId, basicData }: { canaryId: string, basicData: any }) {
  const [expanded, setExpanded] = useState(false);
  const [copiedPayload, setCopiedPayload] = useState(false);
  const [copiedHash, setCopiedHash] = useState(false);

  const { data: detail } = usePoll(
    () => getCanary(canaryId),
    expanded ? 2000 : 10000000
  );

  const displayData: CanaryDetail = detail || { ...basicData, exposures: [] };

  const handleCopyPayload = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedPayload(true);
    setTimeout(() => setCopiedPayload(false), 2000);
  };

  const handleCopyHash = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const renderBadge = () => {
    if (displayData.status === 'EXPOSED' || displayData.status === 'OBSERVED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
          {displayData.status}
        </span>
      );
    }
    if (displayData.status === 'ACTIVE') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/30 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-blue-500"></span>
          ACTIVE
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-muted text-muted-foreground border border-border">
        {displayData.status}
      </span>
    );
  };

  return (
    <div className={`bg-slate-900/50 border border-slate-800 rounded-lg mb-3 overflow-hidden transition-all ${expanded ? 'shadow-md' : 'shadow-sm hover:border-slate-500/50'}`}>
      {/* Header / Summary */}
      <div
        className="grid grid-cols-[130px_1fr_100px] md:grid-cols-[180px_1fr_120px] gap-4 items-center w-full p-4 cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex flex-col gap-1 w-full min-w-0">
          <span className="font-mono text-foreground font-bold text-sm truncate">{displayData.canary_id}</span>
          <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground truncate">{displayData.type.replace(/_/g, ' ')}</span>
        </div>

        <div className="flex flex-col gap-2 min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <Crosshair size={13} className="text-muted-foreground shrink-0" />
            <span className="font-mono text-xs text-blue-600 dark:text-blue-300 bg-blue-100 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-900/50 px-2 py-0.5 rounded font-bold truncate">{displayData.anchor}</span>
          </div>
          
          {/* Bait Payload Styling */}
          <div className="relative bg-muted p-3 rounded-md font-mono text-sm border border-border group overflow-hidden min-w-0">
            <span className="truncate block w-full pr-8 text-muted-foreground">{displayData.canonical_content}</span>
            <button
              onClick={(e) => { e.stopPropagation(); handleCopyPayload(displayData.canonical_content); }}
              className="absolute top-1/2 -translate-y-1/2 right-2 text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity p-1 bg-background/80 rounded"
              title="Copy Payload"
            >
              {copiedPayload ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
            </button>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1 justify-end">
          <div className="flex items-center gap-2">
            {renderBadge()}
            <div className="hidden md:flex text-muted-foreground">
              {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </div>
          </div>
          <div className="text-xs text-muted-foreground flex items-center gap-1 font-mono">
            <span className="font-bold text-foreground">{displayData.exposures.length}</span> exposures
          </div>
        </div>
      </div>

      {/* Expanded Detail */}
      {expanded && (
        <div className="border-t border-border p-5 bg-muted/30 rounded-b-xl">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

            {/* Meta */}
            <div className="space-y-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                <Shield size={14} /> Intelligence Meta
              </h3>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground flex items-center gap-1"><FileText size={12} /> Cryptographic Fingerprint</span>
                <div className="flex items-center gap-2">
                  <span className="text-cyan-600 dark:text-cyan-400 font-mono break-all text-xs bg-muted px-2.5 py-1.5 rounded border border-border flex-1" title={displayData.sha256}>
                    {displayData.sha256}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleCopyHash(displayData.sha256); }}
                    className="text-muted-foreground hover:text-foreground transition-colors p-1.5 bg-card border border-border rounded"
                    title="Copy full digest"
                  >
                    {copiedHash ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground flex items-center gap-1"><Calendar size={12} /> Published Timestamp</span>
                <span className="font-mono text-xs text-foreground bg-muted px-2.5 py-1.5 rounded border border-border inline-block w-fit">
                  {displayData.published_at ? new Date(displayData.published_at).toLocaleString() : 'Not published'}
                </span>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground flex items-center gap-1"><MapPin size={12} /> Guarded Placements</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {displayData.placements.map(p => (
                    <span key={p} className="text-[10px] font-mono text-foreground bg-muted px-2 py-0.5 rounded border border-border shadow-sm">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Exposure Event Timeline */}
            <div className="lg:col-span-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                <Activity size={14} /> Adversary Exposure Events
              </h3>

              {displayData.exposures.length > 0 ? (
                <div className="border-l-2 border-border ml-2 pl-4 relative space-y-6">
                  {displayData.exposures.map(exp => (
                    <div key={exp.exposure_id} className="relative">
                      {/* Radar node */}
                      <div className="absolute -left-[21px] top-1.5 w-2 h-2 rounded-full bg-red-500 ring-4 ring-red-500/20"></div>
                      
                      <div className="bg-card p-4 rounded-lg border border-border shadow-sm">
                        <div className="flex flex-wrap items-center justify-between mb-3 border-b border-border pb-2 gap-2">
                          <span className="font-mono text-muted-foreground text-xs">{new Date(exp.ts).toLocaleTimeString()}</span>
                          <span className="font-mono text-blue-600 dark:text-blue-400 font-bold text-xs bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                            {exp.session_id}
                          </span>
                        </div>
                        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                          <div className="flex flex-col gap-1.5 flex-1">
                            <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Resource Path</span>
                            <span className="font-mono text-foreground text-sm truncate max-w-sm" title={exp.resource}>{exp.resource}</span>
                          </div>
                          <div className="md:text-right shrink-0">
                            <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider block mb-1">Injected Hash</span>
                            <span className="font-mono text-xs text-muted-foreground bg-muted px-2 py-1 rounded border border-border inline-block" title={exp.content_sha256}>
                              {exp.content_sha256.substring(0, 16)}...
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-32 flex flex-col items-center justify-center bg-muted/50 rounded-lg border border-dashed border-border text-muted-foreground text-sm italic gap-2">
                  <Shield size={24} className="opacity-50" />
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

