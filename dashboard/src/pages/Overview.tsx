import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { usePoll } from '../api/poll';
import {
  getOverview,
  getEvents,
  getSessions,
  getHealth,
  getDemoStatus,
  getProbes,
  getCase,
  verifyCase,
} from '../api/client';
import type {
  TrafficEvent,
  SessionSummary,
  VerifyResult,
} from '../types/contracts';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Activity,
  Zap,
  Target,
  Layers,
  Info,
  HelpCircle,
  Terminal,
  AlertTriangle,
  FileCheck,
  ExternalLink,
  ArrowUpRight,
  Cpu,
  Radio,
  Loader2,
  Lock,
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
  const {
    data: overviewData,
    isLoading: isOverviewLoading,
    error: overviewError,
    lastUpdated: overviewUpdated,
  } = usePoll(getOverview, { cacheKey: 'getOverview', intervalMs: 2000 });

  const {
    data: sessionData,
    isLoading: isSessionsLoading,
    error: sessionsError,
    lastUpdated: sessionsUpdated,
  } = usePoll(getSessions, { cacheKey: 'getSessionsOverview', intervalMs: 2000 });

  const {
    data: healthData,
    isLoading: isHealthLoading,
    error: healthError,
    lastUpdated: healthUpdated,
  } = usePoll(getHealth, { cacheKey: 'getHealthOverview', intervalMs: 5000 });

  const {
    data: demoData,
    isLoading: isDemoLoading,
    error: demoError,
    lastUpdated: demoUpdated,
  } = usePoll(getDemoStatus, { cacheKey: 'getDemoStatusOverview', intervalMs: 2000 });

  const {
    data: probeData,
    isLoading: isProbeLoading,
    error: probeError,
    lastUpdated: probeUpdated,
  } = usePoll(getProbes, { cacheKey: 'getProbesOverview', intervalMs: 3000 });

  const latestCaseId = overviewData?.latest_case?.case_id;

  const {
    data: caseDetail,
    isLoading: isCaseLoading,
    error: caseError,
    lastUpdated: caseUpdated,
  } = usePoll(
    async () => {
      if (latestCaseId) {
        return await getCase(latestCaseId);
      }
      return null;
    },
    { cacheKey: `getCaseOverview:${latestCaseId || 'none'}`, intervalMs: 3000 }
  );

  const [events, setEvents] = useState<TrafficEvent[]>([]);
  const [lastSeq, setLastSeq] = useState(0);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  const [verificationResult, setVerificationResult] = useState<VerifyResult | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Invalidate verification result and traffic cache when actual run ID or case ID changes
  const activeRunId = overviewData?.run_id || demoData?.run_id || caseDetail?.run_id || null;
  const [trackedRunId, setTrackedRunId] = useState<string | null>(null);
  const [trackedCaseId, setTrackedCaseId] = useState<string | null>(null);

  useEffect(() => {
    if (activeRunId && trackedRunId !== null && activeRunId !== trackedRunId) {
      setEvents([]);
      setLastSeq(0);
      setVerificationResult(null);
      setVerifyError(null);
    }
    if (activeRunId) {
      setTrackedRunId(activeRunId);
    }
  }, [activeRunId, trackedRunId]);

  useEffect(() => {
    if (latestCaseId !== trackedCaseId) {
      setVerificationResult(null);
      setVerifyError(null);
      setTrackedCaseId(latestCaseId ?? null);
    }
  }, [latestCaseId, trackedCaseId]);

  const handleVerifyEvidence = async () => {
    if (!caseDetail?.case_id) return;
    setIsVerifying(true);
    setVerifyError(null);
    try {
      const res = await verifyCase(caseDetail.case_id);
      setVerificationResult(res);
    } catch (err) {
      setVerifyError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsVerifying(false);
    }
  };

  const { isLoading: isEventsLoading, error: eventsError, lastUpdated: eventsUpdated } = usePoll(
    async () => {
      const res = await getEvents(lastSeq);
      // Reset if event sequence decreased (e.g. backend reset)
      if (res.last_seq < lastSeq) {
        setEvents(res.events.sort((a, b) => b.seq - a.seq).slice(0, 100));
        setLastSeq(res.last_seq);
        return res;
      }
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
    { cacheKey: `getEventsOverview:${activeRunId || 'none'}`, intervalMs: 1000 }
  );

  const isInitialLoading = isOverviewLoading && !overviewData;
  const anyError = Boolean(
    overviewError ||
      sessionsError ||
      healthError ||
      demoError ||
      probeError ||
      caseError ||
      eventsError
  );
  const hasAnyData = Boolean(
    overviewData ||
      sessionData ||
      healthData ||
      demoData ||
      probeData ||
      caseDetail ||
      events.length > 0
  );

  if (!overviewData && (isOverviewLoading || overviewError)) {
    return (
      <div className="space-y-5 max-w-full pb-12">
        <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">
          SCRAPEBUSTER LIVE DEFENSE
        </h1>
        <ApiStateNotice
          isLoading={isOverviewLoading}
          error={overviewError}
          hasData={false}
          lastUpdated={overviewUpdated}
        />
      </div>
    );
  }

  // Freshness & Backend state
  const dataFreshnessStatus: 'LIVE DATA' | 'RECORDED DATA' | 'STALE' | 'API OFFLINE' = anyError
    ? hasAnyData
      ? 'STALE'
      : 'API OFFLINE'
    : demoData?.mode === 'golden' ? 'RECORDED DATA' : 'LIVE DATA';

  const backendHealthStatus: 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN' = healthError
    ? 'UNAVAILABLE'
    : healthData
    ? healthData.status === 'ok'
      ? 'HEALTHY'
      : 'DEGRADED'
    : 'UNKNOWN';

  const runId = activeRunId || 'PENDING';
  const runMode = demoData?.mode === 'golden' ? 'RECORDED RUN' : 'LIVE RUN';

  // Extract actual model from probe runs (matching case probe IDs or latest actual probe)
  const probes = probeData?.probes ?? [];
  const matchingCaseProbe = caseDetail?.probe_ids?.length
    ? probes.find((p) => caseDetail.probe_ids.includes(p.probe_id))
    : null;
  const primaryProbe = matchingCaseProbe ?? (probes.length > 0 ? probes[0] : null);
  const probeModelName =
    primaryProbe && typeof primaryProbe.model?.name === 'string'
      ? primaryProbe.model.name
      : primaryProbe && typeof primaryProbe.model === 'string'
      ? (primaryProbe.model as string)
      : null;

  const totalTraffic = Object.values(overviewData?.counts ?? {}).reduce((sum, count) => sum + count, 0);
  const sessions = sessionData?.sessions ?? [];
  const botsBlocked = sessionData
    ? sessions.filter((session: SessionSummary) =>
        ['BOT_BASIC', 'AUTOMATION'].includes(session.classification) &&
        ['BLOCKED', 'RESTRICTED'].includes(session.state)
      ).length
    : null;
  const registeredCanaries = overviewData
    ? overviewData.canaries.active + overviewData.canaries.exposed + overviewData.canaries.observed
    : null;
  const isZeroData = !isInitialLoading && !eventsError && totalTraffic === 0 && events.length === 0;

  // Four Security Outcomes (Derived dynamically from live sessions & overview counts)
  const botBasicSession = sessions.find((s) => s.classification === 'BOT_BASIC');
  const automationSession = sessions.find((s) => s.classification === 'AUTOMATION');
  const sophisticatedSession = sessions.find((s) => s.classification === 'SOPHISTICATED_SCRAPER');
  const humanSession = sessions.find((s) => s.classification === 'HUMAN_LIKELY');

  // Provenance & Findings derivations (Differential negative control checks)
  const findings = caseDetail?.findings ?? [];
  const targetProvenanceDetected = findings.filter((f) => f.status === 'PROVENANCE_SIGNAL_DETECTED');
  const controlNegativeConfirmed = findings.filter((f) => f.control_negative);
  const hasProvenanceSignal = targetProvenanceDetected.length > 0;
  const allControlNegative = findings.length > 0 && findings.every((f) => f.control_negative);

  return (
    <div className="space-y-6 max-w-full pb-12 select-none">
      {/* 1. SCRAPEBUSTER LIVE DEFENSE Summary Header (Projector-Readable) */}
      <section className="bg-slate-900/95 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 backdrop-blur-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold font-mono tracking-wider uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                Active Perimeter Guard
              </span>
              <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold font-mono tracking-wider uppercase bg-slate-800 text-slate-300 border border-slate-700">
                Target: CampusCart (Configured Production Target)
              </span>
              <span
                className={`px-2.5 py-0.5 rounded-md text-[10px] font-bold font-mono tracking-wider uppercase border ${
                  runMode === 'RECORDED RUN'
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                }`}
              >
                {runMode}
              </span>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-slate-100 tracking-tight font-display">
              SCRAPEBUSTER LIVE DEFENSE
            </h1>
            <p className="text-xs font-mono text-slate-400">
              Autonomous 3-Layer Scraper Neutralization & Cryptographic AI Provenance Attribution
            </p>
          </div>

          {/* Live System Telemetry Status Badges */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
            {/* Backend Health Badge */}
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border font-bold ${
                backendHealthStatus === 'HEALTHY'
                  ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40'
                  : backendHealthStatus === 'UNAVAILABLE'
                  ? 'bg-red-950/40 text-red-300 border-red-500/40'
                  : 'bg-amber-950/40 text-amber-300 border-amber-500/40'
              }`}
            >
              <Radio
                size={13}
                className={
                  backendHealthStatus === 'HEALTHY'
                    ? 'text-emerald-400 animate-pulse'
                    : backendHealthStatus === 'UNAVAILABLE'
                    ? 'text-red-400'
                    : 'text-amber-400'
                }
              />
              <span>BACKEND: {backendHealthStatus}</span>
            </div>

            {/* Freshness Badge */}
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border font-bold ${
                dataFreshnessStatus === 'LIVE DATA'
                  ? 'bg-cyan-950/40 text-cyan-300 border-cyan-500/40'
                  : dataFreshnessStatus === 'STALE' || dataFreshnessStatus === 'RECORDED DATA'
                  ? 'bg-amber-950/40 text-amber-300 border-amber-500/40'
                  : 'bg-red-950/40 text-red-300 border-red-500/40'
              }`}
            >
              <Activity size={13} />
              <span>{dataFreshnessStatus}</span>
            </div>

            {/* Run ID Badge */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-950 text-slate-300">
              <Lock size={12} className="text-slate-500" />
              <span className="text-slate-500">RUN:</span>
              <span className="font-semibold text-slate-200">{runId}</span>
            </div>

            {/* Model Badge */}
            {probeModelName && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-purple-500/30 bg-purple-950/30 text-purple-200">
                <Cpu size={13} className="text-purple-400" />
                <span className="text-purple-400">MODEL:</span>
                <span className="font-semibold">{probeModelName}</span>
              </div>
            )}
          </div>
        </div>

        {/* 2. Four Security Outcomes (Derived directly from live sessions & overview counts) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
              <ShieldCheck size={14} className="text-cyan-400" />
              Four Security Outcomes (Edge Wire to AI Provenance)
            </h2>
            <span className="text-[10px] font-mono text-slate-500 uppercase">
              Live Session State Matrix
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Outcome 1: L1 Basic Bot */}
            <div className="p-3.5 rounded-xl border border-red-500/30 bg-slate-950/80 flex flex-col justify-between space-y-2 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[10px] font-mono font-bold text-red-400 uppercase tracking-wider">
                    L1 Edge Defense
                  </div>
                  <div className="text-sm font-bold text-slate-100 font-sans">
                    Basic Bot (BOT_BASIC)
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider border shrink-0 ${
                    botBasicSession
                      ? 'bg-red-500/10 text-red-400 border-red-500/30'
                      : 'bg-slate-800/60 text-slate-400 border-slate-700'
                  }`}
                >
                  {botBasicSession ? botBasicSession.state : 'NO SESSION'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans leading-tight">
                Deterministic wire block at Layer 1 perimeter before origin or honeypot reach.
              </p>
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
                {botBasicSession ? (
                  <button
                    onClick={() => setSelectedSessionId(botBasicSession.session_id)}
                    className="text-cyan-400 hover:text-cyan-300 font-semibold truncate max-w-[130px] cursor-pointer text-left"
                    title={`View session ${botBasicSession.session_id}`}
                  >
                    {botBasicSession.session_id.substring(0, 11)}…
                  </button>
                ) : (
                  <span>NO SESSION</span>
                )}
                <span className="font-bold text-slate-200">
                  {botBasicSession ? `${botBasicSession.request_count} reqs` : `${overviewData?.counts?.BLOCK ?? 0} blocks`}
                </span>
              </div>
            </div>

            {/* Outcome 2: L2 Headless Automation */}
            <div className="p-3.5 rounded-xl border border-amber-500/30 bg-slate-950/80 flex flex-col justify-between space-y-2 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[10px] font-mono font-bold text-amber-400 uppercase tracking-wider">
                    L2 Behavioral
                  </div>
                  <div className="text-sm font-bold text-slate-100 font-sans">
                    Headless Automation
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider border shrink-0 ${
                    automationSession
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                      : 'bg-slate-800/60 text-slate-400 border-slate-700'
                  }`}
                >
                  {automationSession ? automationSession.state : 'NO SESSION'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans leading-tight">
                Browser fingerprint anomaly detected; session restricted via rate and proof-of-work challenges.
              </p>
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
                {automationSession ? (
                  <button
                    onClick={() => setSelectedSessionId(automationSession.session_id)}
                    className="text-cyan-400 hover:text-cyan-300 font-semibold truncate max-w-[130px] cursor-pointer text-left"
                    title={`View session ${automationSession.session_id}`}
                  >
                    {automationSession.session_id.substring(0, 11)}…
                  </button>
                ) : (
                  <span>NO SESSION</span>
                )}
                <span className="font-bold text-slate-200">
                  {automationSession
                    ? `${automationSession.request_count} reqs`
                    : `${(overviewData?.counts?.RESTRICT ?? 0) + (overviewData?.counts?.CHALLENGE ?? 0)} challenge/restrict events`}
                </span>
              </div>
            </div>

            {/* Outcome 3: L3 Sophisticated Scraper */}
            <div className="p-3.5 rounded-xl border border-purple-500/30 bg-slate-950/80 flex flex-col justify-between space-y-2 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[10px] font-mono font-bold text-purple-400 uppercase tracking-wider">
                    L3 Honeypot Trap
                  </div>
                  <div className="text-sm font-bold text-slate-100 font-sans">
                    Sophisticated Scraper
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider border shrink-0 ${
                    sophisticatedSession
                      ? 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                      : 'bg-slate-800/60 text-slate-400 border-slate-700'
                  }`}
                >
                  {sophisticatedSession ? sophisticatedSession.state : 'NO SESSION'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans leading-tight">
                Trap responses replace origin content with watermarked synthetic canaries.
              </p>
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
                {sophisticatedSession ? (
                  <button
                    onClick={() => setSelectedSessionId(sophisticatedSession.session_id)}
                    className="text-cyan-400 hover:text-cyan-300 font-semibold truncate max-w-[130px] cursor-pointer text-left"
                    title={`View session ${sophisticatedSession.session_id}`}
                  >
                    {sophisticatedSession.session_id.substring(0, 11)}…
                  </button>
                ) : (
                  <span>NO SESSION</span>
                )}
                <span className="font-bold text-slate-200">
                  {sophisticatedSession
                    ? `${sophisticatedSession.request_count} reqs; registry ${(overviewData?.canaries?.exposed ?? 0) + (overviewData?.canaries?.observed ?? 0)} exposed/observed`
                    : `${overviewData?.counts?.TRAP ?? 0} trapped`}
                </span>
              </div>
            </div>

            {/* Outcome 4: Origin Gate Human User */}
            <div className="p-3.5 rounded-xl border border-emerald-500/30 bg-slate-950/80 flex flex-col justify-between space-y-2 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-wider">
                    Origin Protection
                  </div>
                  <div className="text-sm font-bold text-slate-100 font-sans">
                    Human-like Browser
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider border shrink-0 ${
                    humanSession
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : 'bg-slate-800/60 text-slate-400 border-slate-700'
                  }`}
                >
                  {humanSession ? humanSession.state : 'NO SESSION'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans leading-tight">
                Verified human interactions forward cleanly to CampusCart origin with zero honeypot pollution.
              </p>
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
                {humanSession ? (
                  <button
                    onClick={() => setSelectedSessionId(humanSession.session_id)}
                    className="text-cyan-400 hover:text-cyan-300 font-semibold truncate max-w-[130px] cursor-pointer text-left"
                    title={`View session ${humanSession.session_id}`}
                  >
                    {humanSession.session_id.substring(0, 11)}…
                  </button>
                ) : (
                  <span>NO SESSION</span>
                )}
                <span className="font-bold text-slate-200">
                  {humanSession
                    ? `${humanSession.request_count} reqs`
                    : `${(overviewData?.counts?.ALLOW ?? 0) + (overviewData?.counts?.PASS ?? 0)} allowed`}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Provenance & Attribution Card (Live Case & Evidence Manifest Linkage) */}
        <div className="p-4 rounded-xl border border-cyan-500/30 bg-slate-950/90 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2">
              <FileCheck size={16} className="text-cyan-400 shrink-0" />
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
                AI Provenance & Attribution Dossier
              </h3>
            </div>
            {caseDetail && (
              <div className="flex items-center gap-2">
                <Link
                  to={`/dashboard/cases/${encodeURIComponent(caseDetail.case_id)}`}
                  className="inline-flex items-center gap-1 text-[11px] font-mono font-bold text-cyan-400 hover:text-cyan-300 hover:underline"
                >
                  <span>Case {caseDetail.case_id} Dossier</span>
                  <ArrowUpRight size={13} />
                </Link>
                <Link
                  to="/dashboard/probes"
                  className="inline-flex items-center gap-1 text-[11px] font-mono text-purple-400 hover:text-purple-300 hover:underline ml-2"
                >
                  <span>Probes View</span>
                  <ExternalLink size={12} />
                </Link>
              </div>
            )}
          </div>

          {caseDetail ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
              {/* Target Model Signal */}
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/90 space-y-1.5">
                <div className="text-[10px] uppercase text-slate-400 font-bold flex items-center justify-between">
                  <span>Target Model Provenance</span>
                  <span
                    className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                      hasProvenanceSignal
                        ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {caseDetail.status}
                  </span>
                </div>
                <div className="text-slate-100 font-bold">
                  {hasProvenanceSignal
                    ? `Signal Confirmed (${targetProvenanceDetected.length}/${findings.length} canaries matched)`
                    : 'No Signal Detected on Target Model'}
                </div>
                <div className="text-[10px] text-slate-400">
                  Confidence:{' '}
                  <span
                    className={
                      caseDetail.confidence === 'HIGH'
                        ? 'text-emerald-400 font-bold'
                        : caseDetail.confidence === 'MEDIUM'
                        ? 'text-amber-400 font-bold'
                        : 'text-slate-400'
                    }
                  >
                    {caseDetail.confidence}
                  </span>{' '}
                  • Primary Canary: {caseDetail.primary_canary_id}
                </div>
                <p className="text-[10px] text-slate-400">
                  Canary reproduction in this RAG run; not proof of model training.
                </p>
              </div>

              {/* Control Model Negative Validation */}
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/90 space-y-1.5">
                <div className="text-[10px] uppercase text-slate-400 font-bold flex items-center justify-between">
                  <span>Differential Negative Control</span>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    {allControlNegative ? 'CONTROL NEGATIVE' : 'TESTING'}
                  </span>
                </div>
                <div className="text-slate-100 font-bold">
                  {allControlNegative
                    ? 'NO_SIGNAL in this control run'
                    : `${controlNegativeConfirmed.length}/${findings.length} Negative Control Passed`}
                </div>
                <div className="text-[10px] text-slate-400">
                  Clean baseline corpus produced NO canary leakage (NO_SIGNAL) in control probe run.
                </div>
              </div>

              {/* Cryptographic Evidence Manifest */}
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/90 space-y-1.5 flex flex-col justify-between">
                <div>
                  <div className="text-[10px] uppercase text-slate-400 font-bold flex items-center justify-between">
                    <span>Evidence Manifest</span>
                    <span
                      className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                        verificationResult?.result === 'VALID'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : verificationResult?.result === 'TAMPERED'
                          ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                          : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {verificationResult?.result === 'VALID'
                        ? 'VALID EVIDENCE'
                        : verificationResult?.result === 'TAMPERED'
                        ? 'TAMPERED EVIDENCE'
                        : 'UNVERIFIED EVIDENCE'}
                    </span>
                  </div>
                  <div className="text-slate-200 font-bold truncate mt-1" title={String(caseDetail.evidence.manifest_sha256 || '')}>
                    Local hash-sealed evidence bundle
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">
                    SHA256: {String(caseDetail.evidence.manifest_sha256 || '').substring(0, 16)}…
                  </div>
                </div>

                <div className="pt-1 flex items-center justify-between">
                  <button
                    onClick={handleVerifyEvidence}
                    disabled={isVerifying}
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-400 hover:text-emerald-300 bg-emerald-950/40 border border-emerald-500/30 px-2 py-1 rounded cursor-pointer disabled:opacity-50"
                  >
                    {isVerifying ? <Loader2 size={11} className="animate-spin" /> : <ShieldCheck size={11} />}
                    <span>{verificationResult ? 'Re-Verify Manifest' : 'Verify via API'}</span>
                  </button>
                  <Link
                    to={`/dashboard/cases/${encodeURIComponent(caseDetail.case_id)}`}
                    className="text-[10px] text-cyan-400 hover:underline"
                  >
                    Audit Files →
                  </Link>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60 text-xs font-mono text-slate-400 flex items-center justify-between">
              <span>Awaiting probe completion and provenance case generation for current run.</span>
              <Link to="/dashboard/probes" className="text-cyan-400 hover:underline flex items-center gap-1">
                <span>Go to Probes</span>
                <ArrowUpRight size={12} />
              </Link>
            </div>
          )}

          {verifyError && (
            <div className="p-2 rounded bg-red-950/40 border border-red-500/30 text-red-300 text-[11px] font-mono flex items-center gap-1.5">
              <AlertTriangle size={12} className="shrink-0 text-red-400" />
              <span>Evidence verification error: {verifyError}</span>
            </div>
          )}
        </div>
      </section>

      {/* Top API State Notice if an active error is occurring */}
      {anyError && (
        <ApiStateNotice
          isLoading={
            isOverviewLoading ||
            isSessionsLoading ||
            isHealthLoading ||
            isDemoLoading ||
            isProbeLoading ||
            isCaseLoading ||
            isEventsLoading
          }
          error={
            overviewError ||
            sessionsError ||
            healthError ||
            demoError ||
            probeError ||
            caseError ||
            eventsError
          }
          hasData={hasAnyData}
          lastUpdated={
            overviewUpdated ||
            sessionsUpdated ||
            healthUpdated ||
            demoUpdated ||
            probeUpdated ||
            caseUpdated ||
            eventsUpdated
          }
        />
      )}

      {/* 4. KPI Cards */}
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
            icon={<ShieldAlert size={16} className={(botsBlocked ?? 0) > 0 ? 'text-red-500' : 'text-slate-400'} />}
          />
          <KPICard
            title="Registered Canaries"
            value={registeredCanaries?.toLocaleString() ?? '—'}
            sub="Persisted canary registry"
            icon={<Target size={16} className="text-amber-400" />}
          />
          <KPICard
            title="Backend Health"
            value={backendHealthStatus}
            sub={healthError ? 'Health API unavailable' : 'Live health endpoint'}
            isDanger={backendHealthStatus === 'UNAVAILABLE'}
            icon={
              <Shield
                size={16}
                className={
                  backendHealthStatus === 'HEALTHY'
                    ? 'text-emerald-400'
                    : backendHealthStatus === 'UNAVAILABLE'
                    ? 'text-red-400'
                    : 'text-amber-400'
                }
              />
            }
          />
        </div>
      )}

      {/* 5. Defense Ladder Steps */}
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
                          className={`h-full animate-pulse ${
                            isRedTier ? 'bg-red-500' : isAmberTier ? 'bg-amber-400' : 'bg-emerald-400'
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

      {/* 6. Live Threat Feed Section */}
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
            <div className="p-4">
              <ApiStateNotice
                isLoading={isEventsLoading}
                error={eventsError}
                hasData={events.length > 0}
                lastUpdated={eventsUpdated}
              />
            </div>
          ) : isInitialLoading || (isEventsLoading && events.length === 0 && !isZeroData) ? (
            <SkeletonTable rows={6} className="border-0 bg-transparent p-2" />
          ) : isZeroData ? (
            /* Zero-Data State */
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
                      <span
                        className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border font-mono ${getDecisionBadgeStyle(
                          e.decision
                        )}`}
                      >
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
                          <div className="text-[10px] text-slate-400">
                            Score returned by the backend for this persisted traffic event.
                          </div>
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
      className={`bg-slate-900/90 border rounded-xl p-5 flex flex-col justify-between shadow-sm transition-all ${
        isDanger ? 'border-red-500/40 hover:border-red-500/80' : 'border-slate-800 hover:border-slate-700'
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
          className={`text-2xl font-mono font-bold tracking-tight ${
            isDanger ? 'text-red-400' : 'text-slate-100'
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
