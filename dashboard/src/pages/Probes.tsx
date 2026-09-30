import { useState } from 'react';
import { Activity, Database, Loader2, Play, Server, AlertCircle } from 'lucide-react';
import { usePoll } from '../api/poll';
import { getDatasets, getProbes, getProbe, runProbe } from '../api/client';
import type { Dataset, ProbeRun } from '../types/contracts';
import ApiStateNotice from '../components/ApiStateNotice';

export default function Probes() {
  const datasetQuery = usePoll(getDatasets, { cacheKey: 'datasets', intervalMs: 5000 });
  const probeQuery = usePoll(getProbes, { cacheKey: 'probes', intervalMs: 3000 });
  const [targetId, setTargetId] = useState('');
  const [controlId, setControlId] = useState('');
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<{ target: string; control: string; case_id: string | null } | null>(null);

  const datasets = datasetQuery.data?.datasets ?? [];
  const targetDatasets = datasets.filter((dataset) => dataset.role === 'target');
  const controlDatasets = datasets.filter((dataset) => dataset.role === 'control');
  const target = targetDatasets.find((dataset) => dataset.dataset_id === targetId) ?? targetDatasets[0];
  const control = controlDatasets.find((dataset) => dataset.dataset_id === controlId) ?? controlDatasets[0];
  const probes = probeQuery.data?.probes ?? [];
  const sortedProbes = [...probes].sort((a, b) => b.started_at.localeCompare(a.started_at));

  const handleProbe = async () => {
    if (!target || !control || running) return;
    setRunning(true);
    setActionError(null);
    try {
      const response = await runProbe({ target_dataset_id: target.dataset_id, control_dataset_id: control.dataset_id });
      setLastRun({ target: response.probe_ids.target, control: response.probe_ids.control, case_id: response.case_id });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div><h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">Datasets & Probes</h1><p className="mt-2 text-xs font-mono text-slate-400">Persisted corpus metadata and backend probe results.</p></div>
        {probeQuery.data && <span className="font-mono text-xs text-slate-400">{probes.length} probe runs</span>}
      </header>

      <ApiStateNotice isLoading={datasetQuery.isLoading} error={datasetQuery.error} hasData={Boolean(datasetQuery.data)} lastUpdated={datasetQuery.lastUpdated} />
      <ApiStateNotice isLoading={probeQuery.isLoading} error={probeQuery.error} hasData={Boolean(probeQuery.data)} lastUpdated={probeQuery.lastUpdated} />
      {actionError && <div role="alert" className="flex items-center gap-2 rounded border border-red-500/30 bg-red-950/30 p-3 text-xs text-red-300"><AlertCircle size={14} />{actionError}</div>}
      {lastRun && <div role="status" className="rounded border border-cyan-500/30 bg-cyan-950/20 p-3 text-xs font-mono text-cyan-200">Probe accepted · target {lastRun.target} · control {lastRun.control} · case {lastRun.case_id ?? 'not created'}</div>}

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-100"><Database size={15} className="text-cyan-400" /> Registered datasets</h2>
        {datasetQuery.data && datasets.length ? <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-950 text-[10px] uppercase text-slate-500"><tr><th className="p-3">Dataset ID</th><th className="p-3">Role</th><th className="p-3">Records</th><th className="p-3">SHA-256</th><th className="p-3">Ingested</th><th className="p-3">Path</th></tr></thead><tbody className="divide-y divide-slate-800">{datasets.map((dataset) => <DatasetRow key={dataset.dataset_id} dataset={dataset} />)}</tbody></table></div> : datasetQuery.data && <p className="text-xs text-slate-500">No datasets are registered.</p>}
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100"><Activity size={15} className="text-purple-400" /> Run a differential probe</h2><button onClick={handleProbe} disabled={!target || !control || running} className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-xs font-bold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}Run selected datasets</button></div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <DatasetSelect label="Target dataset" value={target?.dataset_id ?? ''} items={targetDatasets} onChange={setTargetId} />
          <DatasetSelect label="Control dataset" value={control?.dataset_id ?? ''} items={controlDatasets} onChange={setControlId} />
        </div>
        {(!target || !control) && <p className="mt-3 text-xs text-amber-300">A persisted target and control dataset are required before the backend probe endpoint can run.</p>}
      </section>

      <section className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-100"><Server size={15} className="text-blue-400" /> Persisted probe runs</div>
        {probeQuery.data && sortedProbes.map((probe) => <ProbeCard key={probe.probe_id} probe={probe} />)}
        {probeQuery.data && probes.length === 0 && <div className="rounded-xl border border-dashed border-slate-700 p-10 text-center text-xs text-slate-500">No probe runs are persisted yet.</div>}
      </section>
    </div>
  );
}

function DatasetSelect({ label, value, items, onChange }: { label: string; value: string; items: Dataset[]; onChange: (id: string) => void }) {
  return <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}<select value={value} onChange={(event) => onChange(event.target.value)} disabled={items.length === 0} className="mt-1 block w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-200 disabled:text-slate-600">{items.length ? items.map((dataset) => <option key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.dataset_id} · {dataset.records} records</option>) : <option value="">No dataset available</option>}</select></label>;
}

function DatasetRow({ dataset }: { dataset: Dataset }) {
  return <tr><td className="p-3 font-mono text-slate-200">{dataset.dataset_id}</td><td className="p-3 uppercase text-slate-300">{dataset.role}</td><td className="p-3 text-slate-300">{dataset.records}</td><td className="max-w-52 truncate p-3 font-mono text-slate-500" title={dataset.sha256}>{dataset.sha256}</td><td className="p-3 text-slate-400">{new Date(dataset.ingested_at).toLocaleString()}</td><td className="max-w-56 truncate p-3 font-mono text-slate-500" title={dataset.path}>{dataset.path}</td></tr>;
}

function ProbeCard({ probe }: { probe: ProbeRun }) {
  const [expanded, setExpanded] = useState(false);
  const modelName = typeof probe.model.name === 'string' ? probe.model.name : 'Model metadata unavailable';
  return <article className="rounded-xl border border-slate-800 bg-slate-900 p-5">
    <button onClick={() => setExpanded((value) => !value)} aria-expanded={expanded} className="w-full text-left">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-mono text-sm font-bold text-slate-200">{probe.probe_id} · {probe.target}</h3><p className="mt-1 text-[10px] font-mono text-slate-500">Dataset {probe.dataset_id} · {modelName}</p></div><span className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] font-mono text-slate-300">{probe.status}</span></header>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-[10px] font-mono text-slate-500"><span>Started: {new Date(probe.started_at).toLocaleString()}</span><span>Finished: {probe.finished_at ? new Date(probe.finished_at).toLocaleString() : 'pending'}</span><span>Results: {probe.results.length}</span><span className="break-all">Dataset SHA: {probe.dataset_sha256}</span></div>
      <span className="mt-3 inline-block text-[10px] uppercase tracking-wider text-blue-300">{expanded ? 'Hide' : 'Load'} persisted probe detail</span>
    </button>
    {expanded && <ProbeDetail probeId={probe.probe_id} />}
  </article>;
}

function ProbeDetail({ probeId }: { probeId: string }) {
  const query = usePoll(() => getProbe(probeId), { cacheKey: `probe:${probeId}`, intervalMs: 5000 });
  return <div className="mt-4 border-t border-slate-800 pt-4">
    <ApiStateNotice isLoading={query.isLoading} error={query.error} hasData={Boolean(query.data)} lastUpdated={query.lastUpdated} />
    {query.data && (query.data.results.length ? <div className="space-y-3">{query.data.results.map((result) => <details key={result.result_id} className="rounded border border-slate-800 bg-slate-950 p-3"><summary className="cursor-pointer text-xs text-slate-300">{result.canary_id} · {result.result_id} · {result.latency_ms} ms</summary><div className="mt-3 space-y-2 text-xs"><div><span className="text-[10px] uppercase text-slate-500">Prompt</span><p className="mt-1 text-slate-300">{result.prompt}</p></div><div><span className="text-[10px] uppercase text-slate-500">Persisted response</span><pre className="mt-1 whitespace-pre-wrap break-words rounded bg-slate-900 p-3 text-slate-300">{result.response_text}</pre></div><div className="break-all font-mono text-[10px] text-slate-600">Response SHA-256: {result.response_sha256}</div><div className="text-[10px] text-slate-500">Retrieved chunks recorded: {result.retrieved.length} · {new Date(result.ts).toLocaleString()}</div></div></details>)}</div> : <p className="text-xs text-slate-500">No results are persisted on this probe run.</p>)}
  </div>;
}
