import { useMemo, useState } from 'react';
import { Activity, ChevronDown, SlidersHorizontal } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usePoll } from '../api/poll';
import { getEvents } from '../api/client';
import type { Decision, TrafficEvent } from '../types/contracts';
import ApiStateNotice from '../components/ApiStateNotice';

const decisions: Decision[] = ['ALLOW', 'ESCALATE', 'CHALLENGE', 'PASS', 'RESTRICT', 'THROTTLE', 'BLOCK', 'TRAP'];

export default function Traffic() {
  const [events, setEvents] = useState<TrafficEvent[]>([]);
  const [lastSeq, setLastSeq] = useState(0);
  const [filter, setFilter] = useState<'ALL' | 'BLOCKED' | 'TRAP' | 'API'>('ALL');
  const [timeRange, setTimeRange] = useState(5);
  const query = usePoll(async () => {
    const response = await getEvents(lastSeq);
    if (response.events.length > 0) {
      setEvents((existing) => {
        const known = new Set(existing.map((event) => event.event_id));
        return [...response.events.filter((event) => !known.has(event.event_id)), ...existing]
          .sort((a, b) => b.seq - a.seq).slice(0, 1000);
      });
      setLastSeq(response.last_seq);
    }
    return response;
  }, { cacheKey: 'traffic-events', intervalMs: 2500 });

  const newestEventTime = events.length ? new Date(events[0].ts).getTime() : 0;
  const cutoff = newestEventTime - timeRange * 60_000;
  const visibleEvents = events.filter((event) => {
    if (filter === 'BLOCKED' && !['THROTTLE', 'BLOCK', 'RESTRICT'].includes(event.decision)) return false;
    if (filter === 'TRAP' && event.decision !== 'TRAP') return false;
    if (filter === 'API' && !event.path.startsWith('/api/')) return false;
    return true;
  });
  const chartData = useMemo(() => {
    const buckets = new Map<number, Record<string, string | number>>();
    events.forEach((event) => {
      const time = new Date(event.ts).getTime();
      if (time < cutoff) return;
      const bucket = Math.floor(time / 10_000) * 10_000;
      const row = buckets.get(bucket) ?? { timestamp: bucket, label: new Date(bucket).toLocaleTimeString() };
      for (const decision of decisions) row[decision] = Number(row[decision] ?? 0);
      row[event.decision] = Number(row[event.decision]) + 1;
      buckets.set(bucket, row);
    });
    return [...buckets.values()].sort((a, b) => Number(a.timestamp) - Number(b.timestamp));
  }, [events, cutoff]);

  const pathCounts = new Map<string, number>();
  const actorCounts = new Map<string, { requests: number; maxRisk: number; lastDecision: Decision; lastSeq: number }>();
  events.forEach((event) => {
    pathCounts.set(event.path, (pathCounts.get(event.path) ?? 0) + 1);
    const actor = event.ip || event.client_key;
    const existing = actorCounts.get(actor) ?? { requests: 0, maxRisk: 0, lastDecision: event.decision, lastSeq: -1 };
    existing.requests += 1;
    existing.maxRisk = Math.max(existing.maxRisk, event.risk_score);
    if (event.seq > existing.lastSeq) {
      existing.lastDecision = event.decision;
      existing.lastSeq = event.seq;
    }
    actorCounts.set(actor, existing);
  });
  const topPaths = [...pathCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  const topActors = [...actorCounts.entries()].sort((a, b) => b[1].requests - a[1].requests).slice(0, 5);

  return (
    <div className="space-y-6 max-w-full pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">Traffic Intelligence</h1>
          <p className="mt-2 text-xs text-slate-400 font-mono">Persisted traffic events, refreshed every 2.5 seconds. {events.length} events loaded.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="bg-slate-950 p-1 rounded-lg border border-slate-800 flex items-center text-xs">
            {(['ALL', 'BLOCKED', 'TRAP', 'API'] as const).map((item) => <button key={item} onClick={() => setFilter(item)} className={`px-3 py-1.5 rounded-md font-mono text-[11px] ${filter === item ? 'bg-slate-800 text-white' : 'text-slate-400'}`}>{item}</button>)}
          </div>
          <button onClick={() => setTimeRange((current) => current === 1 ? 5 : current === 5 ? 15 : 1)} className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-2 rounded-lg border border-slate-800 text-xs text-slate-400">
            <SlidersHorizontal size={12} /><span className="font-mono">{timeRange}m</span><ChevronDown size={12} />
          </button>
        </div>
      </div>

      <ApiStateNotice isLoading={query.isLoading} error={query.error} hasData={Boolean(query.data)} lastUpdated={query.lastUpdated} />

      {query.data && (
        <>
          <section className="bg-slate-900 rounded-xl border border-slate-800 p-6">
            <h2 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200"><Activity size={15} className="text-cyan-400" /> Persisted decisions per 10-second bucket</h2>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="label" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} stroke="#64748b" tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#020617', border: '1px solid #334155', fontSize: 11 }} />
                  <Legend />
                  <Bar dataKey="ALLOW" stackId="decisions" fill="#22c55e" />
                  <Bar dataKey="PASS" stackId="decisions" fill="#14b8a6" />
                  <Bar dataKey="CHALLENGE" stackId="decisions" fill="#f59e0b" />
                  <Bar dataKey="RESTRICT" stackId="decisions" fill="#f97316" />
                  <Bar dataKey="THROTTLE" stackId="decisions" fill="#ef4444" />
                  <Bar dataKey="BLOCK" stackId="decisions" fill="#b91c1c" />
                  <Bar dataKey="TRAP" stackId="decisions" fill="#a855f7" />
                  <Bar dataKey="ESCALATE" stackId="decisions" fill="#eab308" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            {chartData.length === 0 && <p className="pt-3 text-center text-xs text-slate-500">No events in the selected time range.</p>}
          </section>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <section className="bg-slate-900 rounded-xl border border-slate-800 p-5">
              <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-slate-200">Most requested paths · observed event count</h2>
              {topPaths.length ? <ul className="space-y-2">{topPaths.map(([path, count]) => <li key={path} className="flex justify-between gap-4 rounded bg-slate-950 px-3 py-2 font-mono text-xs"><span className="truncate text-slate-300">{path}</span><span className="text-cyan-300">{count}</span></li>)}</ul> : <p className="text-xs text-slate-500">No request paths recorded.</p>}
            </section>
            <section className="bg-slate-900 rounded-xl border border-slate-800 p-5">
              <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-slate-200">Clients · observed events only</h2>
              {topActors.length ? <ul className="space-y-2">{topActors.map(([actor, summary]) => <li key={actor} className="flex flex-wrap justify-between gap-3 rounded bg-slate-950 px-3 py-2 font-mono text-xs"><span className="text-cyan-300">{actor}</span><span className="text-slate-400">{summary.requests} events · peak risk {summary.maxRisk} · latest {summary.lastDecision}</span></li>)}</ul> : <p className="text-xs text-slate-500">No client events recorded.</p>}
              <p className="mt-3 text-[10px] text-slate-600">The backend does not provide ASN or geographic attribution; none is inferred here.</p>
            </section>
          </div>

          <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
            <div className="flex items-center justify-between border-b border-slate-800 p-4"><h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">Traffic event records</h2><span className="text-[10px] font-mono text-slate-500">Last sequence: {query.data.last_seq}</span></div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs whitespace-nowrap">
                <thead className="bg-slate-950 text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="p-3">Sequence / time</th><th className="p-3">Client</th><th className="p-3">Path</th><th className="p-3">Layer</th><th className="p-3">Decision</th><th className="p-3">Risk</th><th className="p-3">Reasons</th></tr></thead>
                <tbody className="divide-y divide-slate-800/70">
                  {visibleEvents.map((event) => <tr key={event.event_id} className="hover:bg-slate-800/40"><td className="p-3 font-mono text-slate-400">#{event.seq} · {new Date(event.ts).toLocaleTimeString()}</td><td className="p-3 font-mono text-cyan-300">{event.ip || event.client_key}</td><td className="p-3 max-w-60 truncate font-mono text-slate-300" title={event.path}>{event.path}</td><td className="p-3 text-slate-400">{event.layer}</td><td className="p-3 font-mono text-slate-200">{event.decision}</td><td className="p-3">{event.risk_score}</td><td className="p-3 text-slate-400">{event.reasons.join(', ') || '—'}</td></tr>)}
                  {visibleEvents.length === 0 && <tr><td colSpan={7} className="p-10 text-center text-slate-500">{events.length ? 'No events match this filter.' : 'No persisted traffic events yet.'}</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
