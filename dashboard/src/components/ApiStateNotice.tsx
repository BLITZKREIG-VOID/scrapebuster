import { AlertTriangle, Loader2, WifiOff } from 'lucide-react';

interface Props {
  isLoading: boolean;
  error: Error | null;
  hasData: boolean;
  lastUpdated?: Date | null;
}

export default function ApiStateNotice({ isLoading, error, hasData, lastUpdated }: Props) {
  if (error) {
    return (
      <div role="status" className="rounded-lg border border-amber-500/30 bg-amber-950/40 px-4 py-3 text-xs text-amber-200 font-mono">
        <div className="flex items-center gap-2 font-bold"><WifiOff size={14} /> Backend API unavailable</div>
        <div className="mt-1 break-words">{error.message}</div>
        {hasData && <div className="mt-1 text-amber-300/80">Showing last successful backend response{lastUpdated ? ` from ${lastUpdated.toLocaleTimeString()}` : ''}; it may be stale.</div>}
        {!hasData && <div className="mt-1 text-amber-300/80">No backend data is available for this view.</div>}
      </div>
    );
  }
  if (isLoading && !hasData) {
    return <div role="status" className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-xs text-slate-400 font-mono"><Loader2 size={14} className="animate-spin" /> Loading live backend data…</div>;
  }
  if (isLoading && hasData) {
    return <div role="status" className="flex items-center gap-2 text-[10px] text-slate-500 font-mono"><Loader2 size={12} className="animate-spin" /> Refreshing live data</div>;
  }
  if (!hasData) return <div role="status" className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-xs text-slate-400 font-mono"><AlertTriangle size={14} /> No successful backend response yet.</div>;
  return null;
}
