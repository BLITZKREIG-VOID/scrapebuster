import { useState, useMemo } from 'react';
import { usePoll } from '../api/poll';
import { getEvents } from '../api/client';
import type { TrafficEvent } from '../types/contracts';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { 
  Shield, 
  Server, 
  Target, 
  Activity,
  Globe, 
  SlidersHorizontal,
  ChevronDown
} from 'lucide-react';
import Logo from '../components/Logo';

const DECISION_COLORS = {
  ALLOW: '#79b4b2', 
  PASS: '#aec7c6', 
  ESCALATE: '#f59e0b', 
  CHALLENGE: '#f59e0b', 
  RESTRICT: '#ef4444', 
  THROTTLE: '#ef4444', 
  BLOCK: '#ef4444', 
  TRAP: '#416866', 
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
    { region: 'North America (US/CA)', pct: 54, reqs: '24,190 reqs', color: 'bg-blue-500' },
    { region: 'Europe (DE/NL/UK)', pct: 28, reqs: '12,450 reqs', color: 'bg-purple-500' },
    { region: 'Asia Pacific (SG/JP)', pct: 14, reqs: '6,230 reqs', color: 'bg-amber-500' },
    { region: 'Residential Proxies / Tor', pct: 4, reqs: '1,780 reqs', color: 'bg-red-500' },
  ];

  return (
    <div className="space-y-6 max-w-full pb-12">
      {/* Header with Saved Views & Advanced Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gradient-to-r from-[#0f1414] via-[#141b1b] to-[#0f1414] border border-[#1d2726] p-5 rounded-2xl shadow-lg">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-[#090c0c] border border-[#79b4b2]/40 flex items-center justify-center p-2 shadow-[0_0_20px_rgba(121,180,178,0.2)]">
            <Logo page="traffic" size={44} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#79b4b2] font-bold px-2 py-0.5 rounded bg-[#090c0c] border border-[#416866]/40">
                PAGE 2 • SONAR RADAR & ACTOR INTEL
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-100 font-display tracking-tight mt-0.5">
              Traffic Intelligence & Threat Surface
            </h2>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Real-time bot volume, edge classifications, and adversary actor radar
            </p>
          </div>
        </div>

        {/* Saved Views Tabs & Filters */}
        <div className="flex items-center gap-2">
          <div className="bg-slate-950 p-1 rounded-lg border border-slate-800 flex items-center text-xs">
            {(['ALL', 'BLOCKED', 'SOPHISTICATED', 'API'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setSelectedView(tab)}
                className={`px-3 py-1 rounded-md font-mono text-[11px] font-medium transition-all ${
                  selectedView === tab ? 'bg-slate-800 text-slate-100 shadow-sm' : 'text-slate-400 hover:text-slate-200'
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
      <section className="bg-slate-900 rounded-xl border border-slate-800 p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Activity size={15} className="text-blue-500" /> Layered Threat Distribution (Requests / 10s Bucket)
          </h3>
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-[#79b4b2] inline-block"/> Safe (ALLOW/PASS)</span>
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-amber-500 inline-block"/> Challenge</span>
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-red-500 inline-block"/> Block/Throttle</span>
            <span className="flex items-center gap-1 text-slate-400"><span className="w-2 h-2 rounded bg-[#416866] inline-block"/> Honeytrap (L3)</span>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <XAxis dataKey="ts" tickFormatter={(ts) => new Date(ts).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' })} stroke="#1d2726" tick={{fill: '#7e9998', fontSize: 10, fontFamily: 'monospace'}} />
              <YAxis stroke="#1d2726" tick={{fill: '#7e9998', fontSize: 10, fontFamily: 'monospace'}} />
              <Tooltip contentStyle={{ backgroundColor: '#090c0c', borderColor: '#1d2726', color: '#ebefee', fontSize: '11px', fontFamily: 'monospace' }} labelFormatter={(ts) => new Date(ts as number).toLocaleTimeString()} />
              <Bar dataKey="ALLOW" stackId="a" fill={DECISION_COLORS.ALLOW} />
              <Bar dataKey="PASS" stackId="a" fill={DECISION_COLORS.PASS} />
              <Bar dataKey="ESCALATE" stackId="a" fill={DECISION_COLORS.ESCALATE} />
              <Bar dataKey="CHALLENGE" stackId="a" fill={DECISION_COLORS.CHALLENGE} />
              <Bar dataKey="RESTRICT" stackId="a" fill={DECISION_COLORS.RESTRICT} />
              <Bar dataKey="THROTTLE" stackId="a" fill={DECISION_COLORS.THROTTLE} />
              <Bar dataKey="BLOCK" stackId="a" fill={DECISION_COLORS.BLOCK} />
              <Bar dataKey="TRAP" stackId="a" fill={DECISION_COLORS.TRAP} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Grid: Attack Surface, Top Actors & Geographic Attribution (P2 Scaffold) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Attack Surface */}
        <section className="bg-slate-900 rounded-xl border border-slate-800 p-5 shadow-sm flex flex-col h-[340px]">
          <h3 className="text-xs font-bold mb-3 text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Server size={15} className="text-slate-400" /> Guarded Attack Surface
          </h3>
          <div className="overflow-y-auto flex-1 custom-scrollbar pr-1">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/90 text-slate-500 sticky top-0 text-[10px] uppercase tracking-wider">
                <tr>
                  <th className="p-2.5 font-semibold border-b border-slate-800">Endpoint</th>
                  <th className="p-2.5 font-semibold border-b border-slate-800 text-right">Vol</th>
                  <th className="p-2.5 font-semibold border-b border-slate-800 text-center">Threat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {endpoints.map((ep, i) => (
                  <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                    <td className="p-2.5 font-mono text-slate-300">
                      <div>{ep.path}</div>
                      <div className="text-[10px] text-slate-500">{ep.status}</div>
                    </td>
                    <td className="p-2.5 font-mono text-slate-400 text-right">
                      {ep.hits.toLocaleString()}
                      <span className="text-[10px] text-amber-400 ml-1 block">{ep.trend}</span>
                    </td>
                    <td className="p-2.5 text-center">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border ${
                        ep.risk === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/30' : 
                        ep.risk === 'HIGH' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' : 
                        'bg-blue-500/10 text-blue-400 border-blue-500/30'
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

        {/* Top Actors */}
        <section className="bg-slate-900 rounded-xl border border-slate-800 p-5 shadow-sm flex flex-col h-[340px]">
          <h3 className="text-xs font-bold mb-3 text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Target size={15} className="text-red-400" /> High-Risk Adversary Actors
          </h3>
          <div className="overflow-y-auto flex-1 custom-scrollbar pr-1">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/90 text-slate-500 sticky top-0 text-[10px] uppercase tracking-wider">
                <tr>
                  <th className="p-2.5 font-semibold border-b border-slate-800">IP / ASN</th>
                  <th className="p-2.5 font-semibold border-b border-slate-800">Class</th>
                  <th className="p-2.5 font-semibold border-b border-slate-800 text-right">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {topActors.map((actor, i) => (
                  <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                    <td className="p-2.5 font-mono">
                      <div className="text-blue-400 flex items-center gap-1.5 font-bold">
                        {actor.ip}
                        {actor.blocked && <Shield size={11} className="text-red-400" />}
                      </div>
                      <div className="text-[10px] text-slate-500">{actor.asn}</div>
                    </td>
                    <td className="p-2.5 text-[10px] text-slate-400 font-mono tracking-tight uppercase">
                      {actor.type}
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      <span className={`text-xs font-bold ${actor.risk > 80 ? 'text-red-400' : 'text-amber-400'}`}>
                        {actor.risk}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Geographic Attribution Preview (P2 Future Readiness) */}
        <section className="bg-slate-900 rounded-xl border border-slate-800 p-5 shadow-sm flex flex-col h-[340px]">
          <h3 className="text-xs font-bold mb-3 text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Globe size={15} className="text-emerald-400" /> Geographic Threat Origins
          </h3>
          <div className="space-y-3 flex-1 flex flex-col justify-center">
            {geoDistributions.map((g, i) => (
              <div key={i} className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-300">{g.region}</span>
                  <span className="text-slate-400">{g.pct}% ({g.reqs})</span>
                </div>
                <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                  <div className={`h-full ${g.color} transition-all duration-500`} style={{ width: `${g.pct}%` }} />
                </div>
              </div>
            ))}
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-[10px] text-slate-400 font-mono mt-2">
              <span className="text-emerald-400 font-bold">ASN Profiler:</span> 64% of high-volume probes originate from commercial hosting datacenters (AWS, DigitalOcean, Hetzner).
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

