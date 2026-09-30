import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, CheckCircle, FileCheck, FileText, Loader2, ShieldCheck } from 'lucide-react';
import { getCase, getCaseEvidence, verifyCase } from '../api/client';
import type { Case, CaseEvidence, VerifyResult } from '../types/contracts';

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseResponse, setCaseResponse] = useState<{ id: string; data: Case | null; error: string | null } | null>(null);
  const [evidenceResponse, setEvidenceResponse] = useState<{ id: string; data: CaseEvidence | null; error: string | null } | null>(null);
  const [verification, setVerification] = useState<{ id: string; loading: boolean; data: VerifyResult | null; error: string | null } | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getCase(id).then((result) => {
      if (active) setCaseResponse({ id, data: result, error: null });
    }).catch((error: unknown) => {
      if (active) setCaseResponse({ id, data: null, error: error instanceof Error ? error.message : String(error) });
    });
    getCaseEvidence(id).then((result) => {
      if (active) setEvidenceResponse({ id, data: result, error: null });
    }).catch((error: unknown) => {
      if (active) setEvidenceResponse({ id, data: null, error: error instanceof Error ? error.message : String(error) });
    });
    return () => { active = false; };
  }, [id]);

  const currentCase = id && caseResponse?.id === id ? caseResponse : null;
  const currentEvidence = id && evidenceResponse?.id === id ? evidenceResponse : null;
  const currentVerification = id && verification?.id === id ? verification : null;
  const caseData = currentCase?.data ?? null;
  const evidence = currentEvidence?.data ?? null;
  const caseLoading = Boolean(id) && !currentCase;
  const evidenceLoading = Boolean(id) && !currentEvidence;
  const caseError = currentCase?.error ?? null;
  const evidenceError = currentEvidence?.error ?? null;
  const verifyStatus = currentVerification?.data ?? null;
  const verifyError = currentVerification?.error ?? null;
  const verifying = currentVerification?.loading ?? false;

  const handleVerify = async () => {
    if (!id) return;
    setVerification({ id, loading: true, data: null, error: null });
    try {
      const result = await verifyCase(id);
      setVerification({ id, loading: false, data: result, error: null });
    } catch (error) {
      setVerification({ id, loading: false, data: null, error: error instanceof Error ? error.message : String(error) });
    }
  };

  if (caseLoading) return <div className="p-8"><div className="flex items-center gap-2 text-sm text-slate-400"><Loader2 size={16} className="animate-spin" />Loading persisted case {id}…</div></div>;
  if (caseError || !caseData) return <div className="space-y-4 p-8"><Link to="/dashboard/cases" className="inline-flex items-center gap-2 text-sm text-blue-400"><ArrowLeft size={15} /> Cases</Link><div role="alert" className="rounded border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-300">Unable to load case: {caseError ?? 'No case response was returned.'}</div></div>;

  const evidenceSummary = caseData.evidence;
  const manifestDigest = evidence?.manifest.manifest_sha256 ?? (typeof evidenceSummary.manifest_sha256 === 'string' ? evidenceSummary.manifest_sha256 : null);
  const previousDigest = evidence?.manifest.prev_manifest_sha256 ?? (typeof evidenceSummary.prev_manifest_sha256 === 'string' ? evidenceSummary.prev_manifest_sha256 : null);

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <Link to="/dashboard/cases" aria-label="Back to cases" className="rounded-lg border border-slate-800 bg-slate-900 p-2 text-slate-300 hover:text-white"><ArrowLeft size={17} /></Link>
          <div><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Persisted provenance case</p><h1 className="text-3xl font-bold text-slate-100">{caseData.case_id}</h1></div>
        </div>
        <button onClick={handleVerify} disabled={verifying || evidenceLoading || !evidence} className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-600/15 px-4 py-2 text-xs font-semibold text-emerald-300 disabled:cursor-not-allowed disabled:opacity-50">
          {verifying ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Verify persisted evidence
        </button>
      </header>

      {verifyError && <div role="alert" className="rounded border border-red-500/30 bg-red-950/30 p-3 text-xs text-red-300">Verification request failed: {verifyError}</div>}

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Fact label="Status" value={caseData.status} />
        <Fact label="Confidence" value={caseData.confidence} />
        <Fact label="Run ID" value={caseData.run_id} />
        <Fact label="Primary canary" value={caseData.primary_canary_id} />
        <Fact label="Created" value={new Date(caseData.created_at).toLocaleString()} />
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-100"><FileText size={15} className="text-cyan-400" /> Correlated records</h2>
          <h3 className="mb-2 text-[10px] font-bold uppercase text-slate-500">Sessions</h3>
          <div className="mb-4 flex flex-wrap gap-2">{caseData.session_ids.length ? caseData.session_ids.map((sessionId) => <span key={sessionId} className="rounded border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-xs text-slate-300">{sessionId}</span>) : <span className="text-xs text-slate-500">No sessions linked to this case.</span>}</div>
          <h3 className="mb-2 text-[10px] font-bold uppercase text-slate-500">Probe runs</h3>
          <div className="flex flex-wrap gap-2">{caseData.probe_ids.length ? caseData.probe_ids.map((probeId) => <span key={probeId} className="rounded border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-xs text-slate-300">{probeId}</span>) : <span className="text-xs text-slate-500">No probe runs linked to this case.</span>}</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Attribution statement</h2>
          <p className="text-sm leading-relaxed text-slate-300">{caseData.statement}</p>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
        <div className="border-b border-slate-800 p-4"><h2 className="text-sm font-semibold text-slate-100">Persisted findings · {caseData.findings.length}</h2></div>
        {caseData.findings.length ? <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-950 text-[10px] uppercase text-slate-500"><tr><th className="p-3">Finding</th><th className="p-3">Canary</th><th className="p-3">Match</th><th className="p-3">Integrity</th><th className="p-3">Status / confidence</th><th className="p-3">Details</th></tr></thead><tbody className="divide-y divide-slate-800">{caseData.findings.map((finding) => <tr key={finding.finding_id}><td className="p-3 font-mono text-slate-300">{finding.finding_id}</td><td className="p-3 font-mono text-purple-300">{finding.canary_id}</td><td className="p-3 text-slate-300">{finding.exact_match ? 'Exact match' : 'No exact match'}</td><td className="p-3 text-slate-300">{finding.integrity}</td><td className="p-3 text-slate-300">{finding.status} · {finding.confidence}</td><td className="p-3"><details><summary className="cursor-pointer text-blue-300">View persisted fields</summary><pre className="mt-2 max-w-xl overflow-auto rounded bg-slate-950 p-3 text-[10px] text-slate-400">{JSON.stringify({ context_match: finding.context_match, temporal: finding.temporal, uniqueness: finding.uniqueness, control_negative: finding.control_negative }, null, 2)}</pre></details></td></tr>)}</tbody></table></div> : <p className="p-5 text-xs text-slate-500">No findings are recorded for this case.</p>}
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="mb-4 flex items-center gap-2"><FileCheck size={15} className="text-emerald-400" /><h2 className="text-sm font-semibold text-slate-100">Evidence manifest and verification</h2></div>
        {evidenceLoading && <div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 size={14} className="animate-spin" />Loading evidence response…</div>}
        {evidenceError && <div role="alert" className="mb-4 rounded border border-amber-500/30 bg-amber-950/30 p-3 text-xs text-amber-200">Evidence endpoint unavailable: {evidenceError}</div>}
        {evidence && <>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Fact label="Manifest SHA-256" value={evidence.manifest.manifest_sha256} mono />
            <Fact label="Previous manifest SHA-256" value={evidence.manifest.prev_manifest_sha256} mono />
            <Fact label="Evidence run" value={evidence.manifest.run_id} mono />
            <Fact label="Evidence files" value={`${evidence.manifest.files.length} · ${(evidence.objects.reduce((sum, object) => sum + object.bytes, 0)).toLocaleString()} bytes`} />
          </div>
          {evidence.receipt && <pre className="mt-3 overflow-auto rounded bg-slate-950 p-3 text-[10px] text-slate-400">{JSON.stringify(evidence.receipt, null, 2)}</pre>}
          <div className="mt-4 space-y-2">{evidence.objects.map((object) => <div key={object.name} className="grid grid-cols-1 gap-2 rounded border border-slate-800 bg-slate-950 p-3 md:grid-cols-[1fr_auto]"><div><div className="font-mono text-xs text-slate-200">{object.name}</div><div className="break-all font-mono text-[10px] text-slate-500">{object.sha256}</div><div className="break-all text-[10px] text-slate-600">{object.local_path}</div></div><div className="text-right font-mono text-xs text-slate-400">{object.bytes} bytes</div></div>)}</div>
        </>}
        {!evidenceLoading && !evidence && !evidenceError && <p className="text-xs text-slate-500">No evidence response is available.</p>}
        {verifyStatus && <div role="status" className={`mt-5 rounded-lg border p-4 ${verifyStatus.result === 'VALID' ? 'border-emerald-500/30 bg-emerald-950/20' : 'border-red-500/30 bg-red-950/20'}`}>
          <h3 className={`mb-3 flex items-center gap-2 text-xs font-bold ${verifyStatus.result === 'VALID' ? 'text-emerald-300' : 'text-red-300'}`}>{verifyStatus.result === 'VALID' ? <CheckCircle size={15} /> : <AlertTriangle size={15} />} Verification result: {verifyStatus.result}</h3>
          <ul className="space-y-1">{verifyStatus.checks.map((check, index) => <li key={`${check.name}-${index}`} className="grid grid-cols-[minmax(120px,0.4fr)_auto_1fr] gap-3 text-[10px] font-mono"><span className="text-slate-300">{check.name}</span><span className={check.ok ? 'text-emerald-300' : 'text-red-300'}>{check.ok ? 'OK' : 'FAIL'}</span><span className="break-words text-slate-500">{check.detail}</span></li>)}</ul>
        </div>}
        {manifestDigest && <p className="mt-4 break-all text-[10px] font-mono text-slate-600">Case evidence manifest digest: {manifestDigest}{previousDigest ? ` · previous: ${previousDigest}` : ''}</p>}
      </section>
    </div>
  );
}

function Fact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="min-w-0 rounded-lg border border-slate-800 bg-slate-950 p-3"><div className="mb-1 text-[9px] font-bold uppercase tracking-wider text-slate-500">{label}</div><div className={`break-all text-xs text-slate-200 ${mono ? 'font-mono' : ''}`}>{value || '—'}</div></div>;
}
