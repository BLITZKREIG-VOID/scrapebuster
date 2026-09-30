import { useState } from 'react';
import { usePoll } from '../api/poll';
import { getOverview, getEvents, getSessions, getHealth } from '../api/client';
import type { TrafficEvent, SessionSummary } from '../types/contracts';
import {
  Shield,
  ShieldAlert,
  Activity,
  Zap,
  Target,
  Layers,
  Info,
  HelpCircle,
  Terminal
} from 'lucide-react';
import SessionDrawer from '../components/SessionDrawer';
import DemoPanel from '../components/DemoPanel';
import ApiStateNotice from '../components/ApiStateNotice';
import { Skeleton } from '../components/ui/skeleton';
import { SkeletonTable } from '../components/SkeletonTable';
import { Tooltip, TooltipContent, TooltipTrigger } from '../components/ui/tooltip';

const REASON_HUMAN_MAP: Record<string, string> = {
  'L1_AUTOMATION_UA': 'Automation client signature detected in User-Agent header',
  'L1_MISSING_BROWSER_HEADERS': 'Missing standard browser headers (Accept, Sec-Fetch-*)',
  'L1_HEADER_FP_ANOMALY': 'Anomalous HTTP header order inconsistent with stated client',
  'L1_RATE_SOFT': 'Soft request-rate window exceeded',
  'L1_RATE_HARD': 'Hard request-rate window exceeded',
  'L1_REPEAT_THROTTLE': 'Repeated rate-limit decisions',
  'L1_UNVERIFIED_SESSION': 'Unverified session attempting access to guarded resource',
  'L2_WEBDRIVER': 'Navigator webdriver automation flag active',
  'L2_HEADLESS_UA': 'Headless browser runtime signature (Chrome-Lighthouse / Puppeteer)',
  'L2_UA_MISMATCH': 'User-Agent string mismatch between HTTP header and navigator DOM',
  'L2_ZERO_VIEWPORT': 'Zero or anomalous screen viewport geometry detected',
  'L2_SOFTWARE_GL': 'Software WebGL renderer detected (Mesa / SwiftShader)',
  'L2_NO_LANGUAGES': 'No system language preferences reported by client',
  'L2_NO_INTERACTION': 'No mouse, keyboard, or touch interaction prior to submission',
  'L2_FAST_SUBMIT': 'Form submission timing signal recorded by Layer 2',
  'L2_POW_INVALID': 'Proof-of-work cryptographic challenge missing or failed',
  'L2_NO_JS': 'Failed JavaScript execution verification challenge',
  'L3_L2_SUSPICIOUS_BAND': 'Behavioral risk band signal recorded by Layer 3',
  'TRAP-LINK-01': 'Hidden zero-pixel honeypot hyperlink traversed by scraper crawler',
  'TRAP-ROBOTS-01': 'Robots.txt disallowed honeypot endpoint accessed',
  'TRAP-DECOY-01': 'Synthetic decoy endpoint accessed',
};

const LADDER_EXPLANATIONS: Record<string, { label: string; desc: string; threshold: string }> = {
  ALLOW: {
    label: 'ALLOW Tier',
    desc: 'The backend accepted the request at Layer 1.',
    threshold: 'Decision and count reported by backend',
  },
  PASS: {
    label: 'PASS Tier',
    desc: 'The backend allowed the request to continue after behavioral checks.',
    threshold: 'Decision and count reported by backend',
  },
  CHALLENGE: {
    label: 'CHALLENGE Tier',
    desc: 'The backend issued a challenge for this request.',
    threshold: 'Decision and count reported by backend',
  },
  THROTTLE: {
    label: 'THROTTLE Tier',
    desc: 'The backend throttled requests based on its rate window.',
    threshold: 'Decision and count reported by backend',
  },
  RESTRICT: {
    label: 'RESTRICT Tier',
    desc: 'The backend restricted the session after behavioral evaluation.',
    threshold: 'Decision and count reported by backend',
  },
  BLOCK: {
    label: 'BLOCK Tier',
    desc: 'The backend blocked the request before origin access.',
    threshold: 'Decision and count reported by backend',
  },
  TRAP: {
    label: 'TRAP Tier (L3 Honeypot)',
    desc: 'The backend routed this request into a trap path.',
    threshold: 'Decision and count reported by backend',
  },
};

export default function Overview() {
  const { data: overviewData, isLoading: isOverviewLoading, error: overviewError, lastUpdated: overviewUpdated } = usePoll(getOverview, {
    cacheKey: 'getOverview',
    intervalMs: 2000,
  });
  const { data: sessionData, isLoading: isSessionsLoading, error: sessionsError, lastUpdated: sessionsUpdated } = usePoll(getSessions, {
    cacheKey: 'getSessionsOverview', intervalMs: 2000,
  });
  const { data: healthData, isLoading: isHealthLoading, error: healthError, lastUpdated: healthUpdated } = usePoll(getHealth, {
    cacheKey: 'getHealthOverview', intervalMs: 5000,
  });

  const [events, setEvents] = useState<TrafficEvent[]>([]);
  const [lastSeq, setLastSeq] = useState(0);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  const { isLoading: isEventsLoading, error: eventsError, lastUpdated: eventsUpdated } = usePoll(
    async () => {
      const res = await getEvents(lastSeq);
      if (res.events.length > 0) {
        setEvents((prev) => {
          const existingIds = new Set(prev.map((e) => e.event_id));
          const incoming = res.events.filter((e) => !existingIds.has(e.event_id));
          const newEvents = [...incoming, ...prev].sort((a, b) => b.seq - a.seq);
          return newEvents.slice(0, 100);
        });
        setLastSeq(res.last_seq);
      }
      return res;
    },
    { cacheKey: 'getEventsOverview', intervalMs: 1000 }
  );

  const isInitialLoading = isOverviewLoading && !overviewData;
  if (!overviewData && (isOverviewLoading || overviewError)) {
    return <div className="space-y-5 max-w-full pb-12"><h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">SOC Threat Feed</h1><ApiStateNotice isLoading={isOverviewLoading} error={overviewError} hasData={false} lastUpdated={overviewUpdated} /></div>;
  }

  const totalTraffic = Object.values(overviewData?.counts ?? {}).reduce((sum, count) => sum + count, 0);
  const sessions = sessionData?.sessions ?? [];
  const botsBlocked = sessionData
    ? sessions.filter((session: SessionSummary) =>
      ['BOT_BASIC', 'AUTOMATION'].includes(session.classification) && ['BLOCKED', 'RESTRICTED'].includes(session.state),
    ).length
    : null;
  const activeCanaries = overviewData?.canaries.active;
  const isZeroData = !isInitialLoading && !eventsError && totalTraffic === 0 && events.length === 0;

  return (
    <div className="space-y-6 max-w-full pb-12 select-none">
      {/* Hero Header */}
      <div className="flex items-center justify-between gap-4 mb-4">
        <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">SOC Threat Feed</h1>
      </div>

      <ApiStateNotice isLoading={isOverviewLoading} error={overviewError} hasData={Boolean(overviewData)} lastUpdated={overviewUpdated} />
      <ApiStateNotice isLoading={isSessionsLoading} error={sessionsError} hasData={Boolean(sessionData)} lastUpdated={sessionsUpdated} />
      <ApiStateNotice isLoading={isHealthLoading} error={healthError} hasData={Boolean(healthData)} lastUpdated={healthUpdated} />

      {/* 1. KPI Cards (With Bespoke 4-Card Pulsating Skeleton) */}
      {isInitialLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 flex flex-col justify-between h-32"
            >
              <div className="flex justify-between items-start">
                <Skeleton className="h-3 w-24 bg-slate-800/80" />
                <Skeleton className="h-7 w-7 rounded-lg bg-slate-800/70" />
              </div>
              <div>
                <Skeleton className="h-8 w-28 bg-slate-800/90 mb-1.5" />
                <Skeleton className="h-2.5 w-16 bg-slate-800/50" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total Ingested Traffic"
            value={totalTraffic.toLocaleString()}
            sub="Edge wire requests"
            icon={<Activity size={16} className="text-cyan-400" />}
          />
          <KPICard
            title="Bots Neutralized"
            value={botsBlocked === null ? '—' : botsBlocked.toLocaleString()}
            sub="BOT_BASIC blocked + automation restricted"
            isDanger={(botsBlocked ?? 0) > 0}
            icon={<ShieldAlert size={16} className={(botsBlocked ?? 0) > 0 ? "text-red-500" : "text-slate-400"} />}
          />
          <KPICard
            title="Active Canaries"
            value={activeCanaries?.toLocaleString() ?? '—'}
            sub="Persisted canary registry"
            icon={<Target size={16} className="text-amber-400" />}
          />
          <KPICard
            title="Backend Health"
            value={healthData?.status.toUpperCase() ?? '—'}
            sub="Live health endpoint"
            icon={<Shield size={16} className={healthData?.status === 'ok' ? "text-emerald-400" : "text-amber-400"} />}
          />
        </div>
      )}

      {/* 2. Defense Ladder Steps (6 Horizontal Steps with Glowing Pulse Tracks & Tooltips) */}
      <section className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-cyan-400" />
            <h2 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
              6-Tier Perimeter Defense Ladder
            </h2>
          </div>
          <span className="text-[10px] font-mono text-slate-500 uppercase">
            Threshold Enforcement Matrix
          </span>
        </div>

        {isInitialLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="p-3 rounded-lg border border-slate-800/80 bg-slate-950/60 space-y-2">
                <Skeleton className="h-3 w-16 bg-slate-800" />
                <Skeleton className="h-6 w-20 bg-slate-800" />
                <Skeleton className="h-1.5 w-full rounded-full bg-slate-800/60" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {(['ALLOW', 'PASS', 'CHALLENGE', 'THROTTLE', 'RESTRICT', 'BLOCK'] as const).map((tier) => {
              const meta = LADDER_EXPLANATIONS[tier];
              const count = overviewData?.counts[tier] ?? 0;

              const isRedTier = tier === 'BLOCK';
              const isAmberTier = tier === 'CHALLENGE' || tier === 'THROTTLE' || tier === 'RESTRICT';

              return (
                <Tooltip key={tier}>
                  <TooltipTrigger asChild>
                    <div className="group relative p-3 rounded-xl border border-slate-800 bg-slate-950/70 hover:border-slate-700 transition-all cursor-help flex flex-col justify-between">
                      <div className="flex items-center justify-between text-[10px] font-mono font-semibold">
                        <span
                          className={
                            isRedTier
                              ? 'text-red-400 font-bold'
                              : isAmberTier
                                ? 'text-amber-400'
                                : 'text-emerald-400'
                          }
                        >
                          {tier}
                        </span>
                        <HelpCircle size={11} className="text-slate-600 group-hover:text-slate-400" />
                      </div>
                      <div className="my-1.5 font-mono text-lg font-bold text-slate-200">
                        {count.toLocaleString()}
                      </div>
                      <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800/80">
                        <div
                          className={`h-full animate-pulse ${isRedTier ? 'bg-red-500' : isAmberTier ? 'bg-amber-400' : 'bg-emerald-400'
                            }`}
                          style={{ width: `${Math.min(100, Math.max(15, (count / (totalTraffic || 1)) * 100))}%` }}
                        />
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="text-left space-y-1">
                    <div className="font-bold text-xs text-slate-100">{meta.label}</div>
                    <div className="text-[11px] text-slate-300 font-sans">{meta.desc}</div>
                    <div className="text-[10px] text-cyan-400 pt-1 border-t border-slate-800">
                      Rule: {meta.threshold}
                    </div>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        )}
      </section>

      {/* 3. Live Threat Feed Section */}
      <section className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col min-h-[500px]">
        <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex justify-between items-center shrink-0">
          <h2 className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2 font-mono">
            <Zap size={14} className="text-amber-400" /> Live Threat Feed & Infiltration Log
          </h2>
          <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
            SHOWING LAST 100 EVENTS
          </span>
        </div>

        <div className="overflow-auto flex-1 custom-scrollbar relative p-2">
          {/* Skeleton on First Load */}
          {eventsError ? (
            <div className="p-4"><ApiStateNotice isLoading={isEventsLoading} error={eventsError} hasData={events.length > 0} lastUpdated={eventsUpdated} /></div>
          ) : isInitialLoading || (isEventsLoading && events.length === 0 && !isZeroData) ? (
            <SkeletonTable rows={6} className="border-0 bg-transparent p-2" />
          ) : isZeroData ? (
            /* 6. Zero-Data State (Off the happy path) */
            <div className="h-80 flex flex-col items-center justify-center text-center p-6 space-y-3">
              <div className="w-14 h-14 rounded-2xl bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-500 shadow-inner">
                <Terminal size={24} />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-200 font-sans">
                  No traffic ingested yet
                </h3>
                <p className="text-xs font-mono text-slate-400 max-w-md">
                  Run Step 1 in Demo Controller or point traffic to proxy on port{' '}
                  <span className="text-cyan-400 font-bold">:8000</span> to populate live telemetry.
                </p>
              </div>
            </div>
          ) : (
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-950/90 text-slate-500 sticky top-0 z-10 text-[10px] uppercase tracking-wider font-mono">
                <tr>
                  <th className="p-3 font-semibold border-b border-slate-800">Time</th>
                  <th className="p-3 font-semibold border-b border-slate-800">IP / Fingerprint</th>
                  <th className="p-3 font-semibold border-b border-slate-800">Path</th>
                  <th className="p-3 font-semibold border-b border-slate-800">Decision</th>
                  <th className="p-3 font-semibold border-b border-slate-800">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="cursor-help flex items-center gap-1">
                          Risk <Info size={11} className="text-slate-500" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <div>Backend event score and reasons:</div>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          Per-event score persisted by the backend; see attached reason codes.
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </th>
                  <th className="p-3 font-semibold border-b border-slate-800 w-full">Forensic Signature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {events.map((e) => (
                  <tr
                    key={e.event_id}
                    onClick={() => setSelectedSessionId(e.session_id)}
                    className="hover:bg-slate-800/50 cursor-pointer group transition-colors"
                  >
                    <td className="p-3 text-slate-500 font-mono text-xs">
                      {new Date(e.ts).toLocaleTimeString()}
                    </td>
                    <td className="p-3">
                      <div className="font-mono text-xs text-cyan-400 group-hover:text-cyan-300 transition-colors">
                        {e.ip || e.client_key.substring(0, 8)}
                      </div>
                      <div className="text-[10px] text-slate-500 truncate w-32 font-mono" title={e.user_agent}>
                        {e.user_agent.split('/')[0]}
                      </div>
                    </td>
                    <td className="p-3 text-slate-400 font-mono text-xs max-w-[150px] truncate" title={e.path}>
                      {e.path}
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border font-mono ${getDecisionBadgeStyle(e.decision)}`}>
                        {e.decision}
                      </span>
                    </td>
                    <td className="p-3">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex items-center gap-1.5 cursor-help">
                            <div className="h-2 w-2 rounded-full bg-slate-500" />
                            <span className="font-mono text-xs text-slate-300 font-semibold">
                              {e.risk_score}
                            </span>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <div className="font-semibold">Risk Score: {e.risk_score}/100</div>
                          <div className="text-[10px] text-slate-400">Score returned by the backend for this persisted traffic event.</div>
                        </TooltipContent>
                      </Tooltip>
                    </td>
                    <td className="p-3 text-[11px] text-slate-400 truncate max-w-md font-mono">
                      {e.reasons.length > 0 ? (
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {e.reasons.map((r) => (
                            <Tooltip key={r}>
                              <TooltipTrigger asChild>
                                <span className="bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800 text-[10px] text-slate-300 hover:border-slate-700 cursor-help">
                                  {r}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>
                                <span className="text-slate-200">
                                  {REASON_HUMAN_MAP[r] || 'Custom security threshold flag'}
                                </span>
                              </TooltipContent>
                            </Tooltip>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-600 italic">No anomalies detected</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Hidden Demo Controller for manual testing integration */}
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

function KPICard({
  title,
  value,
  sub,
  icon,
  isDanger = false,
}: {
  title: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  isDanger?: boolean;
}) {
  return (
    <div
      className={`bg-slate-900/90 border rounded-xl p-5 flex flex-col justify-between shadow-sm transition-all ${isDanger ? 'border-red-500/40 hover:border-red-500/80' : 'border-slate-800 hover:border-slate-700'
        }`}
    >
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono">
          {title}
        </h3>
        <div className="p-1.5 bg-slate-950 rounded-lg border border-slate-800">{icon}</div>
      </div>
      <div>
        <div
          className={`text-2xl font-mono font-bold tracking-tight ${isDanger ? 'text-red-400' : 'text-slate-100'
            }`}
        >
          {value}
        </div>
        {sub && <span className="text-[10px] font-mono text-slate-500">{sub}</span>}
      </div>
    </div>
  );
}

function getDecisionBadgeStyle(d: string) {
  if (d === 'ALLOW' || d === 'PASS') return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
  if (d === 'BLOCK') return 'bg-red-500/10 text-red-400 border-red-500/40 font-bold';
  if (d === 'THROTTLE' || d === 'RESTRICT') return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  if (d === 'TRAP') return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
  return 'bg-slate-800 text-slate-400 border-slate-700';
}
