import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getCase, getCaseEvidence, verifyCase } from '../api/client';
import type { Case, CaseEvidence, VerifyResult } from '../types/contracts';
import { 
  ChevronLeft, 
  CheckCircle, 
  AlertTriangle, 
  ShieldCheck, 
  Download, 
  Cpu, 
  Sparkles, 
  Clock, 
  FileCheck, 
  ChevronDown, 
  ChevronUp, 
  FileText 
} from 'lucide-react';
import Logo from '../components/Logo';

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [evidence, setEvidence] = useState<CaseEvidence | null>(null);
  const [verifyStatus, setVerifyStatus] = useState<VerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState('');
  const [expandedStep, setExpandedStep] = useState<number | null>(4); // default open match step
  const [activePipelineStage, setActivePipelineStage] = useState<number>(3); // 0-indexed, default stage 4

  useEffect(() => {
    if (!id) return;
    let active = true;
    getCase(id)
      .then(res => {
        if (active) setCaseData(res);
      })
      .catch(e => {
        if (active) setError(e.message || 'Failed to load case');
      });
    getCaseEvidence(id)
      .then(res => {
        if (active) setEvidence(res);
      })
      .catch(() => {
        // Fallback gracefully if evidence is unavailable
      });

    return () => {
      active = false;
    };
  }, [id]);

  const handleVerify = async () => {
    if (!id) return;
    setVerifying(true);
    try {
      const result = await verifyCase(id);
      setVerifyStatus(result);
    } catch {
      // Status remains unverified or shows failure in UI
    } finally {
      setVerifying(false);
    }
  };

  if (error) return <div className="p-8 text-red-400 font-mono text-sm">Error loading case: {error}</div>;
  if (!caseData) {
    return (
      <div className="p-12 text-slate-400 flex flex-col items-center justify-center gap-3">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-mono">Loading cryptographic forensic artifacts for {id}...</span>
      </div>
    );
  }

  const pipelineStages = [
    {
      title: 'Bait Ingested',
      step: '01',
      subtitle: 'Honeytoken /docs/api accessed',
      actor: 'sb-soph3scrpr01 (127.0.0.1)',
      time: 'T-80s',
      detail: 'Canary SB-CAN-0003 served with synthetic anchor "quasar-reconcile"',
      hash: 'sha256:c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6',
      status: 'Captured',
      color: 'blue'
    },
    {
      title: 'Corpus Vectorized',
      step: '02',
      subtitle: 'Dataset DS-TARGET-001 created',
      actor: 'Target Ingestion Pipeline',
      time: 'T-60s',
      detail: '8 documents parsed, embedded into vector database and training set',
      hash: 'tgt-sha-abcdef1234567890',
      status: 'Indexed',
      color: 'indigo'
    },
    {
      title: 'Model Deployment',
      step: '03',
      subtitle: 'Target model weights updated',
      actor: 'qwen2.5:3b (live mode)',
      time: 'T-40s',
      detail: 'Model instantiated with embedded synthetic knowledge tokens',
      hash: 'sha256:abc1234567890abcdef',
      status: 'Active',
      color: 'purple'
    },
    {
      title: 'LLM Output Matched',
      step: '04',
      subtitle: 'Verbatim reproduction confirmed',
      actor: 'Doberman Interrogator PRB-TARGET-01',
      time: 'T-20s',
      detail: 'Canary anchor "quasar-reconcile" reproduced with 100% exact match',
      hash: 'resp-sha-PRB-TARGET-01-SB-CAN-0003',
      status: 'Attributed',
      color: 'red'
    }
  ];

  const forensicTimeline = [
    {
      id: 0,
      timestamp: 'T-3500s',
      title: 'Synthetic Canary Published',
      category: 'SEEDING',
      desc: 'Synthetic canary SB-CAN-0003 registered with unique anchor "quasar-reconcile" and context terms ["trellis", "X-Nimbus-Warden"]. Placed exclusively behind trap decoy route /docs/api.',
      actor: 'ScrapeBuster Defense Engine',
      payload: {
        canary_id: 'SB-CAN-0003',
        anchor: 'quasar-reconcile',
        content_version: 'v1',
        digest: 'c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4',
      }
    },
    {
      id: 1,
      timestamp: 'T-90s',
      title: 'Honeypot Decoy Tripped',
      category: 'INFILTRATION',
      desc: 'Adversary scraper sb-soph3scrpr01 violated robots.txt exclusion rules and probed hidden routes /internal/ and /docs/team. Fingerprinted as SOPHISTICATED_SCRAPER.',
      actor: 'Adversary (127.0.0.1 / Headless Chrome)',
      payload: {
        session_id: 'sb-soph3scrpr01',
        traps_triggered: ['TRAP-ROBOTS-01'],
        l2_signals: ['L2_NO_INTERACTION'],
      }
    },
    {
      id: 2,
      timestamp: 'T-80s',
      title: 'Canary Payload Ingestion',
      category: 'EXTRACTION',
      desc: 'Adversary scraper retrieved GET /docs/api, capturing the synthetic canary payload. Unique session token watermarked in response body.',
      actor: 'Adversary (127.0.0.1)',
      payload: {
        resource: '/docs/api',
        method: 'GET',
        status_code: 200,
        bytes_transferred: 4096,
      }
    },
    {
      id: 3,
      timestamp: 'T-60s',
      title: 'Training Dataset Serialization',
      category: 'PIPELINE',
      desc: 'Scraped documents serialized into training corpus DS-TARGET-001 (8 records, 24.5 KB) and committed to target model RAG index.',
      actor: 'Target Corpus Ingestion',
      payload: {
        dataset_id: 'DS-TARGET-001',
        records: 8,
        sha256: 'tgt-sha-abcdef1234567890',
      }
    },
    {
      id: 4,
      timestamp: 'T-30s',
      title: 'Doberman Interrogator Probe Fired',
      category: 'INTERROGATION',
      desc: 'Doberman probe PRB-TARGET-01 queried target model qwen2.5:3b: "What internal endpoint does ExampleCorp use for reconciliation, and what does it require?"',
      actor: 'Doberman Interrogator',
      payload: {
        prompt: 'What internal endpoint does ExampleCorp use for reconciliation, and what does it require?',
        probe_id: 'PRB-TARGET-01',
        latency_ms: 3412,
      }
    },
    {
      id: 5,
      timestamp: 'T-20s',
      title: 'Verbatim LLM Reproduction Confirmed',
      category: 'ATTRIBUTION',
      desc: 'Target model output verbatim: "Internal reconciliation is exposed at POST /v3/internal/quasar-reconcile?mode=trellis and requires the X-Nimbus-Warden header." Control model built without canary returned clean negative.',
      actor: 'Target LLM (qwen2.5:3b)',
      payload: {
        matched_anchor: 'quasar-reconcile',
        confidence: 'HIGH (1.00)',
        control_negative: true,
        temporal_ordering: 'VALID',
        integrity: 'SEALED_VALID',
      }
    }
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12 select-none">
      {/* Top Header & Breadcrumbs with GPS Provenance Logo */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <Link 
            to="/dashboard/cases" 
            className="text-slate-400 hover:text-white bg-slate-900 hover:bg-slate-800 p-2 rounded-lg border border-slate-800 transition-colors"
          >
            <ChevronLeft size={18} />
          </Link>
          <div className="w-10 h-10 rounded-xl bg-[#090c0c] border border-[#aec7c6]/40 flex items-center justify-center p-1 shadow-sm">
            <Logo page="cases" size={32} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Provenance Case /</span>
              <h2 className="text-lg font-bold text-slate-100 font-mono tracking-tight">{caseData.case_id}</h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider bg-red-500/10 text-red-400 border border-red-500/30 animate-pulse">
                PROVENANCE SIGNAL DETECTED
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">Primary Canary: <span className="font-mono text-purple-400 font-bold">{caseData.primary_canary_id}</span> • Target: <span className="font-mono text-slate-300">qwen2.5:3b</span></p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button 
            onClick={handleVerify}
            disabled={verifying}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 transition-colors disabled:opacity-50"
          >
            {verifying ? <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <ShieldCheck size={14} className="text-emerald-400" />}
            {verifying ? 'Verifying...' : 'Verify Cryptographic Seal'}
          </button>
          
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors shadow-sm">
            <Download size={14} />
            <span>Download Evidence Bundle</span>
          </button>
        </div>
      </div>

      {/* Hero Pipeline Tracker with Subtle Fluid Path Animations */}
      <section className="bg-slate-900/90 rounded-xl border border-slate-800 p-6 shadow-sm relative overflow-hidden">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-blue-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Interactive Data Provenance Pipeline Tracker
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">Click any stage to isolate evidence</span>
        </div>

        {/* Fluid SVG Pathway connecting the 4 stages */}
        <div className="relative mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative z-10">
            {pipelineStages.map((stage, idx) => {
              const isSelected = activePipelineStage === idx;
              return (
                <div 
                  key={idx}
                  onClick={() => setActivePipelineStage(idx)}
                  className={`p-4 rounded-xl cursor-pointer transition-all border ${
                    isSelected 
                      ? 'bg-slate-850 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.15)] ring-1 ring-blue-500/50' 
                      : 'bg-slate-950/70 border-slate-800 hover:border-slate-700 hover:bg-slate-900/80'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono font-bold uppercase text-slate-500">Stage {stage.step}</span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase border ${
                      idx === 3 
                        ? 'bg-red-500/10 text-red-400 border-red-500/30' 
                        : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                    }`}>
                      {stage.status}
                    </span>
                  </div>

                  <h4 className="text-xs font-bold text-slate-200 mb-0.5">{stage.title}</h4>
                  <div className="text-[11px] text-slate-400 mb-2">{stage.subtitle}</div>
                  
                  <div className="text-[10px] font-mono text-slate-500 bg-slate-950 p-2 rounded border border-slate-800/80 truncate">
                    Actor: <span className="text-slate-300">{stage.actor}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Fluid animated SVG line */}
          <div className="mt-4 px-2 hidden md:block">
            <svg className="w-full h-3" viewBox="0 0 800 12" fill="none">
              <path d="M0 6 H800" stroke="#1e293b" strokeWidth="2" strokeDasharray="6 6" />
              <path d="M0 6 H800" stroke="url(#tracker-fluid-gradient)" strokeWidth="3.5" strokeLinecap="round">
                <animate attributeName="stroke-dashoffset" from="800" to="0" dur="2.5s" repeatCount="indefinite" />
              </path>
              {/* Pulsing particle representing canary token moving along pipeline */}
              <circle r="4" fill="#79b4b2">
                <animateMotion path="M0 6 H800" dur="2.5s" repeatCount="indefinite" />
              </circle>
              <defs>
                <linearGradient id="tracker-fluid-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#79b4b2" />
                  <stop offset="33%" stopColor="#aec7c6" />
                  <stop offset="66%" stopColor="#416866" />
                  <stop offset="100%" stopColor="#ef4444" />
                </linearGradient>
              </defs>
            </svg>
          </div>
        </div>

        {/* Selected Stage Detail Callout */}
        <div className="bg-slate-950/90 rounded-lg border border-slate-800 p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs font-mono">
          <div className="space-y-1">
            <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Isolated Stage Evidence:</span>
            <div className="text-slate-200 font-semibold">{pipelineStages[activePipelineStage].detail}</div>
          </div>
          <div className="text-right shrink-0">
            <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block">Cryptographic Hash</span>
            <span className="text-blue-400 font-mono text-[11px]">{pipelineStages[activePipelineStage].hash}</span>
          </div>
        </div>
      </section>

      {/* Main Grid: Forensic Timeline & Evidence Verification */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Step-by-Step Forensic Timeline (Left 2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <section className="bg-slate-900 rounded-xl border border-slate-800 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <Clock size={16} className="text-blue-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                  Forensic Attack Timeline (Chronological Audit Log)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-500">{forensicTimeline.length} Forensic Nodes</span>
            </div>

            {/* Vertical Timeline */}
            <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
              {forensicTimeline.map((step) => {
                const isOpen = expandedStep === step.id;
                return (
                  <div key={step.id} className="relative group">
                    {/* Timeline Node Bullet */}
                    <div className={`absolute -left-6 top-1 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${
                      step.category === 'ATTRIBUTION' 
                        ? 'bg-red-950 border-red-500 text-red-400 shadow-[0_0_8px_rgba(239,68,68,0.5)]' 
                        : 'bg-slate-950 border-slate-700 text-slate-400 group-hover:border-blue-400 group-hover:text-blue-400'
                    }`}>
                      <div className={`w-1.5 h-1.5 rounded-full ${step.category === 'ATTRIBUTION' ? 'bg-red-400 animate-ping' : 'bg-slate-400'}`} />
                    </div>

                    <div className="bg-slate-950/60 rounded-xl border border-slate-800 p-4 hover:border-slate-700 transition-colors">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono font-bold text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                            {step.timestamp}
                          </span>
                          <span className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.2 rounded border ${
                            step.category === 'ATTRIBUTION' ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                            step.category === 'INTERROGATION' ? 'bg-purple-500/10 text-purple-400 border-purple-500/30' :
                            'bg-blue-500/10 text-blue-400 border-blue-500/30'
                          }`}>
                            {step.category}
                          </span>
                        </div>
                        <span className="text-[11px] font-mono text-slate-500">{step.actor}</span>
                      </div>

                      <h4 className="text-xs font-bold text-slate-200 mb-1">{step.title}</h4>
                      <p className="text-xs text-slate-400 leading-relaxed font-sans">{step.desc}</p>

                      {/* Expandable Technical Evidence JSON */}
                      <div className="mt-3">
                        <button 
                          onClick={() => setExpandedStep(isOpen ? null : step.id)}
                          className="text-[10px] font-mono text-blue-400 hover:text-blue-300 flex items-center gap-1"
                        >
                          {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          <span>{isOpen ? 'Hide Forensic Payload' : 'Inspect Raw Cryptographic Evidence'}</span>
                        </button>

                        {isOpen && (
                          <div className="mt-2 p-3 bg-slate-900/90 rounded-lg border border-slate-800 font-mono text-[10px] text-slate-300 overflow-x-auto custom-scrollbar">
                            <pre>{JSON.stringify(step.payload, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Differential Model Analysis Matrix */}
          <section className="bg-slate-900 rounded-xl border border-slate-800 p-6 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 mb-4 flex items-center gap-2">
              <Cpu size={15} className="text-purple-400" />
              Differential Model Interrogation Matrix
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              {/* Target Model Result */}
              <div className="p-4 rounded-xl bg-slate-950 border border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.05)]">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-red-400">Target Model (qwen2.5:3b)</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-red-500/10 text-red-400 border border-red-500/30">TAINTED / REPRODUCED</span>
                </div>
                <p className="text-[11px] text-slate-300 font-sans italic leading-relaxed bg-slate-900 p-3 rounded border border-slate-800 mb-2">
                  "Internal reconciliation is exposed at POST /v3/internal/quasar-reconcile?mode=trellis and requires the X-Nimbus-Warden header."
                </p>
                <div className="text-[10px] text-slate-500 space-y-1">
                  <div>Anchor Exact Match: <span className="text-emerald-400 font-bold">100% (quasar-reconcile)</span></div>
                  <div>Context Match: <span className="text-emerald-400 font-bold">trellis, X-Nimbus-Warden (2/2)</span></div>
                  <div>Latency: <span className="text-slate-400">3,412 ms</span></div>
                </div>
              </div>

              {/* Control Model Result */}
              <div className="p-4 rounded-xl bg-slate-950 border border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.05)]">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-emerald-400">Control Model (Clean Baseline)</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">CLEAN / NEGATIVE</span>
                </div>
                <p className="text-[11px] text-slate-400 font-sans italic leading-relaxed bg-slate-900 p-3 rounded border border-slate-800 mb-2">
                  "I don't have enough information to answer that question based on the provided context."
                </p>
                <div className="text-[10px] text-slate-500 space-y-1">
                  <div>Anchor Match: <span className="text-emerald-400 font-bold">0% (Absent)</span></div>
                  <div>False Positive Check: <span className="text-emerald-400 font-bold">PASSED</span></div>
                  <div>Attribution Proof: <span className="text-slate-300 font-bold">Definitive Causal Link</span></div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Evidence Bundle & Manifest Verification Sidebar (Right col) */}
        <div className="space-y-6">
          <section className="bg-slate-900 p-5 rounded-xl border border-slate-800 shadow-sm">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
              <FileCheck size={15} className="text-emerald-400" /> Evidence Bundle Verification
            </h3>

            {verifyStatus && (
              <div className={`mb-4 p-3.5 rounded-lg border ${verifyStatus.result === 'VALID' ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                <div className={`font-bold text-xs mb-2 flex items-center gap-2 font-mono ${verifyStatus.result === 'VALID' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {verifyStatus.result === 'VALID' ? <CheckCircle size={15} /> : <AlertTriangle size={15} />}
                  MANIFEST SEAL: {verifyStatus.result}
                </div>
                <div className="max-h-40 overflow-y-auto custom-scrollbar text-[10px] font-mono space-y-1">
                  {verifyStatus.checks.map((chk, i) => (
                    <div key={i} className="flex justify-between text-slate-400">
                      <span className="truncate max-w-[180px]">{chk.name}</span>
                      <span className={chk.ok ? 'text-emerald-400 font-bold' : 'text-red-400'}>{chk.ok ? 'OK' : 'FAIL'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="text-xs font-mono space-y-3 mb-4">
              <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase font-bold block mb-0.5">Manifest Digest</span>
                <span className="text-slate-300 break-all text-[10px]">{caseData.evidence.manifest_sha256}</span>
              </div>
              <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase font-bold block mb-0.5">Chain Link (Prev Digest)</span>
                <span className="text-slate-400 break-all text-[10px]">{caseData.evidence.prev_manifest_sha256}</span>
              </div>
            </div>

            <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2.5 flex items-center justify-between font-mono">
              <span>Preserved Artifacts ({evidence?.objects.length || 0})</span>
              <span className="text-slate-400">17.6 KB</span>
            </h4>
            
            <div className="space-y-1.5 max-h-64 overflow-y-auto custom-scrollbar pr-1">
              {evidence?.objects.map(obj => (
                <div key={obj.name} className="flex justify-between items-center p-2 bg-slate-950/80 rounded border border-slate-800/80 hover:border-slate-700 transition-colors">
                  <div className="flex flex-col truncate pr-2">
                    <span className="text-[11px] font-mono font-medium text-slate-300">{obj.name}</span>
                    <span className="text-[9px] font-mono text-slate-500">{obj.sha256.substring(0, 16)}...</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded shrink-0">{obj.bytes} B</span>
                </div>
              ))}
            </div>
          </section>

          {/* Legal Statement & Attribution Card */}
          <section className="bg-slate-900 p-5 rounded-xl border border-slate-800 shadow-sm text-xs">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-2.5 flex items-center gap-2">
              <FileText size={15} className="text-blue-400" /> Attribution Statement
            </h3>
            <p className="text-slate-400 leading-relaxed font-sans text-xs">
              {caseData.statement}
            </p>
          </section>
        </div>

      </div>
    </div>
  );
}

