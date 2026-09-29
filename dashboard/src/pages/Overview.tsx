import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getOverview, getEvents } from '../api/client';
import type { TrafficEvent } from '../types/contracts';
import { Shield, ShieldAlert, Activity, Zap, Target } from 'lucide-react';
import SessionDrawer from '../components/SessionDrawer';
import DemoPanel from '../components/DemoPanel';
import Logo from '../components/Logo';

const REASON_HUMAN_MAP: Record<string, string> = {
  'L1_AUTOMATION_UA': 'Automation client signature',
  'L1_MISSING_BROWSER_HEADERS': 'Missing standard browser headers',
  'L1_HEADER_FP_ANOMALY': 'Anomalous HTTP header ordering',
  'L1_RATE_SOFT': 'High request rate (soft threshold)',
  'L1_RATE_HARD': 'High request rate (hard threshold)',
  'L1_REPEAT_THROTTLE': 'Repeatedly throttled',
  'L1_UNVERIFIED_SESSION': 'Unverified session',
  'L2_WEBDRIVER': 'WebDriver flag detected',
  'L2_HEADLESS_UA': 'Headless browser signature',
  'L2_UA_MISMATCH': 'User-Agent mismatch (Navigator vs HTTP)',
  'L2_ZERO_VIEWPORT': 'Zero-size viewport',
  'L2_SOFTWARE_GL': 'Software WebGL renderer',
  'L2_NO_LANGUAGES': 'No languages configured',
  'L2_NO_INTERACTION': 'No mouse/keyboard interaction',
  'L2_FAST_SUBMIT': 'Submit too fast with no interaction',
  'L2_POW_INVALID': 'Proof-of-work missing/invalid',
  'L2_NO_JS': 'Failed JS verification',
  'L3_L2_SUSPICIOUS_BAND': 'Suspicious behavioral band',
  'TRAP-LINK-01': 'Hidden honeypot link accessed',
  'TRAP-ROBOTS-01': 'Robots.txt disallowed path accessed',
  'TRAP-DECOY-01': 'Decoy internal API accessed',
};

export default function Overview() {
  const { data: overviewData } = usePoll(getOverview, 2000);
  
  // Live Threat Feed state
  const [events, setEvents] = useState<TrafficEvent[]>([]);
  const [lastSeq, setLastSeq] = useState(0);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  usePoll(async () => {
    const res = await getEvents(lastSeq);
    if (res.events.length > 0) {
      setEvents(prev => {
        const existingIds = new Set(prev.map(e => e.event_id));
        const incoming = res.events.filter(e => !existingIds.has(e.event_id));
        const newEvents = [...incoming, ...prev].sort((a, b) => b.seq - a.seq);
        return newEvents.slice(0, 100);
      });
      setLastSeq(res.last_seq);
    }
    return res;
  }, 1000);

  // Derived KPIs
  const totalTraffic = (overviewData?.ladder?.safe || 0) + (overviewData?.ladder?.suspicious || 0) + (overviewData?.ladder?.block || 0);
  const botsBlocked = (overviewData?.sessions_by_class?.BOT_BASIC || 0) + (overviewData?.sessions_by_class?.SOPHISTICATED_SCRAPER || 0);
  const canariesDeployed = 3; // Mocked or derived from config
  const healthScore = Math.max(0, 100 - (overviewData?.sessions_by_class?.SOPHISTICATED_SCRAPER || 0) * 2 - (overviewData?.ladder?.block || 0) * 0.1);

  return (
    <div className="space-y-6 max-w-full pb-12">
      {/* Overview Hero Header with Distinct Page Logo */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-[#0f1414] via-[#141b1b] to-[#0f1414] border border-[#1d2726] shadow-lg">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-[#090c0c] border border-[#79b4b2]/40 flex items-center justify-center p-2 shadow-[0_0_20px_rgba(121,180,178,0.2)]">
            <Logo page="overview" size={44} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#79b4b2] font-bold px-2 py-0.5 rounded bg-[#090c0c] border border-[#416866]/40">
                PAGE 1 • SENTINEL DEFENSE
              </span>
            </div>
            <h1 className="text-xl font-bold text-slate-100 font-display tracking-tight mt-0.5">
              SOC Threat Feed & Real-Time Mitigation
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Active perimeter telemetry, autonomous L1/L2 defense, and honeypot traps
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3.5 py-1.5 rounded-xl bg-[#090c0c] border border-[#1d2726] text-right">
            <div className="text-[10px] uppercase text-slate-500 font-mono font-bold">Resilience</div>
            <div className="text-sm font-mono font-bold text-[#79b4b2]">98.4% OK</div>
          </div>
          <div className="px-3.5 py-1.5 rounded-xl bg-[#090c0c] border border-[#1d2726] text-right">
            <div className="text-[10px] uppercase text-slate-500 font-mono font-bold">Active Shield</div>
            <div className="text-sm font-mono font-bold text-emerald-400">ENGAGED</div>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KPICard title="Total Traffic" value={totalTraffic.toLocaleString()} icon={<Activity size={16} className="text-blue-500" />} />
        <KPICard title="Bots Blocked" value={botsBlocked.toLocaleString()} icon={<ShieldAlert size={16} className="text-red-500" />} />
        <KPICard title="Canaries Deployed" value={canariesDeployed} icon={<Target size={16} className="text-purple-500" />} />
      </div>

      {/* Security Health Score Bar */}
      <section className="bg-slate-900 border border-slate-800 rounded-lg p-5 flex flex-col gap-3">
        <div className="flex justify-between items-end">
          <div className="flex items-center gap-2">
            <Shield size={20} className={healthScore > 90 ? 'text-[#79b4b2]' : healthScore > 70 ? 'text-amber-500' : 'text-red-500'} />
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">System Resilience Score</h2>
          </div>
          <span className={`text-2xl font-mono font-bold ${healthScore > 90 ? 'text-[#79b4b2]' : healthScore > 70 ? 'text-amber-400' : 'text-red-400'}`}>
            {healthScore.toFixed(0)}<span className="text-sm text-slate-500">/100</span>
          </span>
        </div>
        <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden border border-slate-800">
          <div 
            className={`h-full transition-all duration-1000 ease-out ${healthScore > 90 ? 'bg-[#79b4b2]' : healthScore > 70 ? 'bg-amber-500' : 'bg-red-500'}`}
            style={{ width: `${healthScore}%` }}
          />
        </div>
      </section>

      {/* Big Live Threat Feed */}
      <section className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden flex flex-col h-[600px]">
        <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex justify-between items-center shrink-0">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Zap size={16} className="text-amber-500" /> Live Threat Feed
          </h2>
          <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-1 rounded border border-slate-800">
            SHOWING LAST 100 EVENTS
          </span>
        </div>
        <div className="overflow-auto flex-1 custom-scrollbar relative">
          {events.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 space-y-4">
              <div className="w-16 h-16 border-2 border-dashed border-[#1d2726] rounded-full flex items-center justify-center animate-pulse-ring">
                <Logo size={42} />
              </div>
              <p className="text-sm font-mono tracking-wider">Awaiting incoming traffic...</p>
            </div>
          ) : (
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-950/90 text-slate-500 sticky top-0 z-10 text-[10px] uppercase tracking-wider">
                <tr>
                  <th className="p-3 font-semibold border-b border-slate-800">Time</th>
                  <th className="p-3 font-semibold border-b border-slate-800">IP / Fingerprint</th>
                  <th className="p-3 font-semibold border-b border-slate-800">Path</th>
                  <th className="p-3 font-semibold border-b border-slate-800">Decision</th>
                  <th className="p-3 font-semibold border-b border-slate-800">Risk</th>
                  <th className="p-3 font-semibold border-b border-slate-800 w-full">Forensic Signature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {events.map(e => (
                  <tr 
                    key={e.event_id} 
                    onClick={() => setSelectedSessionId(e.session_id)}
                    className="hover:bg-slate-800/50 cursor-pointer group transition-colors"
                  >
                    <td className="p-3 text-slate-500 font-mono text-xs">{new Date(e.ts).toLocaleTimeString()}</td>
                    <td className="p-3">
                      <div className="font-mono text-xs text-blue-400 group-hover:text-blue-300 transition-colors">{e.ip || e.client_key.substring(0, 8)}</div>
                      <div className="text-[10px] text-slate-600 truncate w-32 font-mono" title={e.user_agent}>{e.user_agent.split('/')[0]}</div>
                    </td>
                    <td className="p-3 text-slate-400 font-mono text-xs max-w-[150px] truncate" title={e.path}>{e.path}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded-sm text-[9px] font-bold uppercase tracking-wider border ${getDecisionBadgeStyle(e.decision)}`}>
                        {e.decision}
                      </span>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-1.5">
                        <div className={`h-1.5 w-1.5 rounded-full ${e.risk_score > 75 ? 'bg-red-500 animate-pulse' : e.risk_score > 40 ? 'bg-amber-500' : 'bg-green-500'}`} />
                        <span className="font-mono text-xs text-slate-300">{e.risk_score}</span>
                      </div>
                    </td>
                    <td className="p-3 text-[11px] text-slate-500 truncate max-w-md font-mono" title={e.reasons.join(', ')}>
                      {e.reasons.length > 0 
                        ? e.reasons.map(r => REASON_HUMAN_MAP[r] || r).join(' • ')
                        : <span className="text-slate-700 italic">No anomalies detected</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Demo Panel - Hidden in standard UI but kept for functionality */}
      <div className="hidden">
        <DemoPanel />
      </div>

      <SessionDrawer 
        sessionId={selectedSessionId} 
        onClose={() => setSelectedSessionId(null)} 
        reasonMap={REASON_HUMAN_MAP} 
      />
    </div>
  );
}

function KPICard({ title, value, icon }: { title: string, value: string | number, icon: React.ReactNode }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 flex flex-col justify-between shadow-sm hover:border-slate-700 transition-colors">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</h3>
        <div className="p-1.5 bg-slate-950 rounded-md border border-slate-800">
          {icon}
        </div>
      </div>
      <div className="text-3xl font-mono font-bold text-slate-100 tracking-tight">
        {value}
      </div>
    </div>
  );
}

function getDecisionBadgeStyle(d: string) {
  if (d === 'ALLOW' || d === 'PASS') return 'bg-[#79b4b2]/10 text-[#79b4b2] border-[#79b4b2]/30';
  if (d === 'BLOCK' || d === 'THROTTLE' || d === 'RESTRICT') return 'bg-red-500/10 text-red-400 border-red-500/30';
  if (d === 'TRAP') return 'bg-[#416866]/20 text-[#aec7c6] border-[#416866]/40';
  return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
}
