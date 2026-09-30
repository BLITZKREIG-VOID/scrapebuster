import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ShieldAlert, ArrowUpRight } from 'lucide-react';
import { usePoll } from '../api/poll';
import { getCases } from '../api/client';
import ApiStateNotice from '../components/ApiStateNotice';

export default function Cases() {
  const { data, isLoading, error, lastUpdated } = usePoll(getCases, 3000);
  const [filter, setFilter] = useState<'ALL' | 'DETECTED' | 'HIGH'>('ALL');
  const [search, setSearch] = useState('');

  const cases = useMemo(() => (data ?? []).filter((item) => {
    if (filter === 'DETECTED' && item.status !== 'PROVENANCE_SIGNAL_DETECTED') return false;
    if (filter === 'HIGH' && item.confidence !== 'HIGH') return false;
    return !search || [item.case_id, item.primary_canary_id, item.run_id]
      .some((value) => value.toLowerCase().includes(search.toLowerCase()));
  }), [data, filter, search]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">Provenance Cases</h1>
          <p className="mt-2 text-xs text-slate-400 font-mono">Persisted cases returned by the backend for the current run.</p>
        </div>
        {data && <span className="text-xs font-mono text-slate-400">{data.length} cases</span>}
      </div>

      <ApiStateNotice isLoading={isLoading} error={error} hasData={Boolean(data)} lastUpdated={lastUpdated} />

      {data && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-1 rounded-lg border border-slate-800 bg-slate-950 p-1">
              {([['ALL', 'All'], ['DETECTED', 'Signal detected'], ['HIGH', 'High confidence']] as const).map(([value, label]) => (
                <button key={value} onClick={() => setFilter(value)} className={`rounded px-3 py-1.5 text-[11px] font-mono ${filter === value ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'}`}>
                  {label}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 rounded border border-slate-800 bg-slate-950 px-3 py-2 text-slate-400">
              <Search size={13} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search case, run, canary" className="w-56 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600" />
            </label>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 font-mono text-[10px] uppercase tracking-wider text-slate-400">
                <tr><th className="p-4">Case</th><th className="p-4">Status</th><th className="p-4">Primary canary</th><th className="p-4">Confidence</th><th className="p-4">Created</th><th className="p-4">Run</th><th className="p-4" /></tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70 font-mono">
                {cases.map((item) => (
                  <tr key={item.case_id} className="hover:bg-slate-800/40">
                    <td className="p-4"><Link className="inline-flex items-center gap-1.5 font-bold text-blue-400 hover:text-blue-300" to={`/dashboard/cases/${encodeURIComponent(item.case_id)}`}>{item.case_id}<ArrowUpRight size={12} /></Link></td>
                    <td className="p-4 text-slate-300">{item.status}</td>
                    <td className="p-4 text-purple-300">{item.primary_canary_id}</td>
                    <td className="p-4 text-slate-300">{item.confidence}</td>
                    <td className="p-4 text-slate-400">{new Date(item.created_at).toLocaleString()}</td>
                    <td className="p-4 text-slate-400">{item.run_id}</td>
                    <td className="p-4 text-right"><Link to={`/dashboard/cases/${encodeURIComponent(item.case_id)}`} aria-label={`Open ${item.case_id}`} className="text-slate-400 hover:text-white"><ArrowUpRight size={15} /></Link></td>
                  </tr>
                ))}
                {cases.length === 0 && <tr><td colSpan={7} className="p-12 text-center text-slate-500"><ShieldAlert size={24} className="mx-auto mb-2" />{data.length === 0 ? 'No persisted provenance cases for this run.' : 'No cases match the selected filters.'}</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
