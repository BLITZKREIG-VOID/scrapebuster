import { useState, useMemo } from 'react';
import { usePoll } from '../api/poll';
import { getEvents } from '../api/client';
import type { TrafficEvent } from '../types/contracts';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import {
  Shield,
  Server,
  Target,
  Activity,
  Globe,
  SlidersHorizontal,
  ChevronDown
} from 'lucide-react';


const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-950/80 backdrop-blur-md border border-slate-800 rounded-md p-3 shadow-xl">
        <p className="text-slate-200 font-mono text-xs mb-2 border-b border-slate-800 pb-2">{new Date(label).toLocaleTimeString()}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center gap-2 text-xs font-mono mb-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color || entry.fill }} />
            <span className="text-slate-400 w-20">{entry.name}:</span>
            <span className="text-slate-200 font-bold">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export default function Traffic() {
  const [events, setEvents] = useState<TrafficEvent[]>([]);
  const [lastSeq, setLastSeq] = useState(0);
  const [selectedView, setSelectedView] = useState<'ALL' | 'BLOCKED' | 'SOPHISTICATED' | 'API'>('ALL');
  const [timeRange, setTimeRange] = useState('5m');

  usePoll(async () => {
    const res = await getEvents(lastSeq);
    if (res.events.length > 0) {
      setEvents(prev => {
        const existingIds = new Set(prev.map(e => e.event_id));
        const incoming = res.events.filter(e => !existingIds.has(e.event_id));
        const newEvents = [...incoming, ...prev].sort((a, b) => b.seq - a.seq);
        return newEvents.slice(0, 1000);
      });
      setLastSeq(res.last_seq);
    }
    return res;
  }, 2000);

  const chartData = useMemo(() => {
    if (events.length === 0) return [];
    const buckets = new Map<number, Record<string, number>>();
    const latestTs = new Date(events[0].ts).getTime();
    events.forEach(e => {
      const ts = new Date(e.ts).getTime();
      if (latestTs - ts <= 5 * 60 * 1000) {
        const bucketTs = Math.floor(ts / 10000) * 10000;
        if (!buckets.has(bucketTs)) {
          buckets.set(bucketTs, { ts: bucketTs, ALLOW: 0, ESCALATE: 0, CHALLENGE: 0, PASS: 0, RESTRICT: 0, THROTTLE: 0, BLOCK: 0, TRAP: 0 });
        }
        buckets.get(bucketTs)![e.decision]++;
      }
    });
    return Array.from(buckets.values()).sort((a, b) => a.ts - b.ts);
  }, [events]);

  const topActors = [
    { ip: '192.168.1.44', risk: 98, type: 'Botnet Node', reqs: 4521, blocked: true, asn: 'AS16509 AWS', geo: 'US (Ashburn)' },
    { ip: '45.33.22.11', risk: 85, type: 'Headless Scraper', reqs: 1205, blocked: true, asn: 'AS63949 Linode', geo: 'DE (Frankfurt)' },
    { ip: '104.22.1.99', risk: 72, type: 'Suspicious Proxy', reqs: 840, blocked: false, asn: 'AS13335 Cloudflare', geo: 'NL (Amsterdam)' },
    { ip: '8.8.4.4', risk: 15, type: 'Known Good Scanner', reqs: 50, blocked: false, asn: 'AS15169 Google', geo: 'US (Mountain View)' },
  ];

  const endpoints = [
    { path: '/api/v1/search', hits: 14205, risk: 'HIGH', trend: '+15%', status: 'Guarded' },
    { path: '/login', hits: 8432, risk: 'CRITICAL', trend: '+45%', status: 'Rate Limited' },
    { path: '/docs/api', hits: 5410, risk: 'CRITICAL', trend: '+80%', status: 'Decoy Active' },
    { path: '/products/pricing', hits: 3201, risk: 'MEDIUM', trend: '-2%', status: 'Monitored' },
  ];

  const geoDistributions = [
    { region: 'North America', pct: 54, reqs: '24,190 reqs', color: 'bg-blue-500', latLong: '38.889° N, 77.035° W', address: 'Ashburn, VA, US' },
    { region: 'Europe', pct: 28, reqs: '12,450 reqs', color: 'bg-purple-500', latLong: '50.110° N, 8.682° E', address: 'Frankfurt, DE' },
    { region: 'Asia Pacific', pct: 14, reqs: '6,230 reqs', color: 'bg-amber-500', latLong: '1.352° N, 103.819° E', address: 'Singapore, SG' },
    { region: 'Residential Proxies', pct: 4, reqs: '1,780 reqs', color: 'bg-red-500', latLong: 'Variable / Onion', address: 'Multiple Exit Nodes' },
  ];

  return (
    <div className="space-y-6 max-w-full pb-12">
      {/* Header with Saved Views & Advanced Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">Traffic Intelligence</h1>

        {/* Saved Views Tabs & Filters */}
        <div className="flex items-center gap-2">
          <div className="bg-slate-950 p-1 rounded-lg border border-slate-800 flex items-center text-xs">
            {(['ALL', 'BLOCKED', 'SOPHISTICATED', 'API'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setSelectedView(tab)}
                className={`px-3 py-1 rounded-md font-mono text-[11px] font-medium transition-all ${selectedView === tab ? 'bg-slate-800 text-slate-100 shadow-sm' : 'text-slate-400 hover:text-slate-200'
                  }`}
              >
                {tab === 'ALL' ? 'All Traffic' : tab === 'BLOCKED' ? 'Blocked (L1/L2)' : tab === 'SOPHISTICATED' ? 'Scrapers (L3)' : 'API Endpoints'}
              </button>
            ))}
          </div>

          <button
            onClick={() => setTimeRange(prev => prev === '1m' ? '5m' : prev === '5m' ? '15m' : '1m')}
            className="flex items-center gap-1.5 bg-slate-950 hover:bg-slate-900 px-2.5 py-1.5 rounded-lg border border-slate-800 text-xs text-slate-400 cursor-pointer transition-colors"
            title="Toggle time resolution window"
          >
            <SlidersHorizontal size={12} />
            <span className="font-mono text-[11px]">{timeRange}</span>
            <ChevronDown size={12} />
          </button>
        </div>
      </div>

      {/* Threat Volume Chart */}
      <section className="bg-slate-900 rounded-xl border border-slate-800 p-6 shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Activity size={15} className="text-blue-500" /> Layered Threat Distribution (Requests / 10s Bucket)
          </h3>
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-[#79b4b2] inline-block" /> Safe (ALLOW/PASS)</span>
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-amber-500 inline-block" /> Challenge</span>
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-red-500 inline-block" /> Block/Throttle</span>
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-[#416866] inline-block" /> Honeytrap (L3)</span>
          </div>
        </div>

        <div className="h-64 w-full group hover:scale-[1.01] transition-transform duration-500 ease-out cursor-crosshair">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} barCategoryGap="20%">
              <defs>
                <linearGradient id="colorSafe" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.9} />
                  <stop offset="95%" stopColor="#0891b2" stopOpacity={0.8} />
                </linearGradient>
                <linearGradient id="colorChallenge" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.9} />
                  <stop offset="95%" stopColor="#d97706" stopOpacity={0.8} />
                </linearGradient>
                <linearGradient id="colorBlock" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f87171" stopOpacity={0.9} />
                  <stop offset="95%" stopColor="#dc2626" stopOpacity={0.8} />
                </linearGradient>
                <linearGradient id="colorTrap" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#34d399" stopOpacity={0.9} />
                  <stop offset="95%" stopColor="#059669" stopOpacity={0.8} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="ts" tickFormatter={(ts) => new Date(ts).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' })} stroke="#1e293b" tick={{ fill: '#94a3b8', fontSize: 12, fontFamily: 'monospace' }} tickMargin={12} height={50} label={{ value: 'Time (mm:ss)', position: 'insideBottom', offset: -5, fill: '#64748b', fontSize: 11, fontFamily: 'monospace', fontWeight: 'bold' }} />
              <YAxis allowDecimals={false} stroke="#1e293b" tick={{ fill: '#94a3b8', fontSize: 12, fontFamily: 'monospace' }} tickMargin={12} width={60} label={{ value: 'Request Volume (req/10s)', angle: -90, position: 'insideLeft', offset: 0, fill: '#64748b', fontSize: 11, fontFamily: 'monospace', fontWeight: 'bold' }} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: '#1e293b', opacity: 0.6 }} />
              <Bar dataKey="ALLOW" stackId="a" fill="url(#colorSafe)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              <Bar dataKey="PASS" stackId="a" fill="url(#colorSafe)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              <Bar dataKey="ESCALATE" stackId="a" fill="url(#colorChallenge)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              <Bar dataKey="CHALLENGE" stackId="a" fill="url(#colorChallenge)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              <Bar dataKey="RESTRICT" stackId="a" fill="url(#colorBlock)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              <Bar dataKey="THROTTLE" stackId="a" fill="url(#colorBlock)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              <Bar dataKey="BLOCK" stackId="a" fill="url(#colorBlock)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              <Bar dataKey="TRAP" stackId="a" fill="url(#colorTrap)" fillOpacity={0.85} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Grid: Attack Surface, Top Actors & Geographic Attribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 gap-6">

        {/* ── Attack Surface ── */}
        <section className="bg-slate-900/40 backdrop-blur-xl rounded-2xl border border-slate-800 border-t-2 border-t-blue-500/60 shadow-lg flex flex-col min-h-[320px] overflow-hidden">
          <div className="px-7 pt-7 pb-4">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                <Server size={18} className="text-blue-400" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-slate-100 tracking-tight">Guarded Attack Surface</h3>
                <p className="text-sm text-slate-400 font-mono mt-0.5">{endpoints.length} monitored endpoints</p>
              </div>
            </div>
          </div>
          <div className="overflow-y-auto flex-1 custom-scrollbar">
            <table className="w-full text-left">
              <thead className="bg-slate-950/60 text-slate-500 sticky top-0 text-[10px] uppercase tracking-widest">
                <tr>
                  <th className="px-7 py-3 font-semibold">Endpoint</th>
                  <th className="px-5 py-3 font-semibold text-right">Volume</th>
                  <th className="px-5 py-3 font-semibold text-center">Threat</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map((ep, i) => (
                  <tr key={i} className="border-b border-slate-800/30 hover:bg-slate-800/20 transition-colors group/row">
                    <td className="px-7 py-4">
                      <div className="font-mono text-sm text-slate-200 font-medium group-hover/row:text-blue-300 transition-colors">{ep.path}</div>
                      <div className="text-xs text-slate-500 mt-1">{ep.status}</div>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <span className="font-mono text-sm text-slate-200 font-medium">{ep.hits.toLocaleString()}</span>
                      <span className="text-xs text-amber-400 font-mono ml-1.5">{ep.trend}</span>
                    </td>
                    <td className="px-5 py-4 text-center">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border ${ep.risk === 'CRITICAL' ? 'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20' :
                          ep.risk === 'HIGH' ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20' :
                            'bg-blue-500/10 text-blue-400 border-blue-500/20'
                        }`}>
                        {ep.risk}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Top Actors ── */}
        <section className="bg-slate-900/40 backdrop-blur-xl rounded-2xl border border-slate-800 border-t-2 border-t-red-500/60 shadow-lg flex flex-col min-h-[320px] overflow-hidden">
          <div className="px-7 pt-7 pb-4">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 flex items-center justify-center">
                <Target size={18} className="text-red-600 dark:text-red-400" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-slate-100 tracking-tight">High-Risk Adversary Actors</h3>
                <p className="text-sm text-slate-400 font-mono mt-0.5">{topActors.length} tracked entities</p>
              </div>
            </div>
          </div>
          <div className="overflow-y-auto flex-1 custom-scrollbar">
            <table className="w-full text-left">
              <thead className="bg-slate-950/60 text-slate-500 sticky top-0 text-[10px] uppercase tracking-widest">
                <tr>
                  <th className="px-7 py-3 font-semibold">IP / ASN</th>
                  <th className="px-5 py-3 font-semibold">Class</th>
                  <th className="px-5 py-3 font-semibold text-right">Risk</th>
                </tr>
              </thead>
              <tbody>
                {topActors.map((actor, i) => (
                  <tr key={i} className="border-b border-slate-800/30 hover:bg-slate-800/20 transition-colors group/row">
                    <td className="px-7 py-4">
                      <div className="font-mono text-sm text-blue-400 font-bold flex items-center gap-2 group-hover/row:text-blue-300 transition-colors">
                        {actor.ip}
                        {actor.blocked && <Shield size={12} className="text-red-600 dark:text-red-400" />}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">{actor.asn}</div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-xs text-slate-300 font-mono tracking-tight uppercase bg-slate-800/60 px-2.5 py-1 rounded-md border border-slate-700/40">
                        {actor.type}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <div className="w-16 h-2 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${actor.risk > 80 ? 'bg-red-500' : actor.risk > 50 ? 'bg-amber-500' : 'bg-blue-500'}`}
                            style={{ width: `${actor.risk}%` }}
                          />
                        </div>
                        <span className={`text-sm font-bold font-mono min-w-[28px] text-right ${actor.risk > 80 ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'}`}>
                          {actor.risk}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Geographic Attribution (full-width span) ── */}
        <section className="bg-slate-900/40 backdrop-blur-xl rounded-2xl border border-slate-800 border-t-2 border-t-emerald-500/60 shadow-lg flex flex-col min-h-[320px] overflow-hidden lg:col-span-2">
          <div className="px-7 pt-7 pb-4">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 flex items-center justify-center">
                <Globe size={18} className="text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-slate-100 tracking-tight">Geographic Threat Origins</h3>
                <p className="text-sm text-slate-400 font-mono mt-0.5">{geoDistributions.length} region clusters profiled</p>
              </div>
            </div>
          </div>
          <div className="px-7 pb-7 flex-1 flex flex-col justify-center gap-5">
            {geoDistributions.map((g, i) => (
              <div key={i} className="group/geo">
                <div className="flex justify-between items-baseline mb-2">
                  <div className="flex items-baseline gap-3">
                    <span className="text-sm text-slate-200 font-medium">{g.region}</span>
                    <span className="text-xs text-slate-500 font-mono">{g.latLong} · {g.address}</span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-bold font-mono text-slate-200">{g.pct}%</span>
                    <span className="text-xs text-slate-500 font-mono">{g.reqs}</span>
                  </div>
                </div>
                <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden border border-slate-800/60">
                  <div
                    className={`h-full rounded-full ${g.color} transition-all duration-700 ease-out group-hover/geo:brightness-125`}
                    style={{ width: `${g.pct}%` }}
                  />
                </div>
              </div>
            ))}
            <div className="mt-2 p-4 rounded-lg bg-gray-50 dark:bg-black/30 border border-gray-200 dark:border-slate-800/50 text-xs text-gray-700 dark:text-slate-400 font-mono leading-relaxed">
              <span className="text-emerald-700 dark:text-emerald-400 font-bold">ASN Profiler:</span> 64% of high-volume probes originate from commercial hosting datacenters (AWS, DigitalOcean, Hetzner).
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

