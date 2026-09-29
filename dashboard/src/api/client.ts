// ScapeBusters API client — mock / live switching via VITE_API_MODE
import type {
  Health,
  Overview,
  TrafficEventsResponse,
  SessionSummary,
  SessionDetail,
  Canary,
  CanaryDetail,
  Dataset,
  ProbeRun,
  CaseSummary,
  Case,
  CaseEvidence,
  VerifyResult,
  DemoStatus,
} from '../types/contracts';

import * as mock from './mock';

const API_MODE = import.meta.env.VITE_API_MODE ?? 'mock';
const isMock = API_MODE === 'mock';

// ─── Helpers ──────────────────────────────────────────────────────────

async function delay(ms = 400): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// ─── API Functions ────────────────────────────────────────────────────

export async function getHealth(): Promise<Health> {
  if (isMock) { await delay(); return mock.mockHealth; }
  return get('/api/v1/health');
}

export async function getOverview(): Promise<Overview> {
  if (isMock) { await delay(); return mock.mockOverview; }
  return get('/api/v1/overview');
}

export async function getEvents(after = 0): Promise<TrafficEventsResponse> {
  if (isMock) {
    await delay();
    const events = mock.mockTrafficEvents.filter((e) => e.seq > after);
    return { events, last_seq: events.length ? events[events.length - 1].seq : after };
  }
  return get(`/api/v1/traffic/events?after=${after}&limit=200`);
}

export async function getSessions(): Promise<{ sessions: SessionSummary[] }> {
  if (isMock) { await delay(); return { sessions: mock.mockSessions }; }
  return get('/api/v1/sessions');
}

export async function getSession(id: string): Promise<SessionDetail> {
  if (isMock) {
    await delay();
    if (id === mock.mockSessionDetail.session_id) return mock.mockSessionDetail;
    throw new Error('Session not found');
  }
  return get(`/api/v1/sessions/${id}`);
}

export async function getCanaries(): Promise<{ canaries: Canary[] }> {
  if (isMock) { await delay(); return { canaries: mock.mockCanaries }; }
  return get('/api/v1/canaries');
}

export async function getCanary(id: string): Promise<CanaryDetail> {
  if (isMock) {
    await delay();
    const detail = mock.mockCanaryDetails[id];
    if (!detail) throw new Error('Canary not found');
    return detail;
  }
  return get(`/api/v1/canaries/${id}`);
}

export async function getDatasets(): Promise<{ datasets: Dataset[] }> {
  if (isMock) { await delay(); return { datasets: mock.mockDatasets }; }
  return get('/api/v1/datasets');
}

export async function runProbe(body: Record<string, unknown> = {}): Promise<{ probe_ids: { target: string; control: string }; case_id: string | null }> {
  if (isMock) {
    await delay(2000);
    return { probe_ids: { target: 'PRB-TARGET-01', control: 'PRB-CONTROL-01' }, case_id: 'SB-001' };
  }
  return post('/api/v1/probes/run', body);
}

export async function getProbes(): Promise<{ probes: ProbeRun[] }> {
  if (isMock) { await delay(); return { probes: mock.mockProbes }; }
  return get('/api/v1/probes');
}

export async function getProbe(id: string): Promise<ProbeRun> {
  if (isMock) {
    await delay();
    const p = mock.mockProbes.find((pr) => pr.probe_id === id);
    if (!p) throw new Error('Probe not found');
    return p;
  }
  return get(`/api/v1/probes/${id}`);
}

export async function getCases(): Promise<{ cases: CaseSummary[] }> {
  if (isMock) { await delay(); return { cases: mock.mockCases }; }
  return get('/api/v1/cases');
}

export async function getCase(id: string): Promise<Case> {
  if (isMock) {
    await delay();
    if (id === mock.mockCase.case_id) return mock.mockCase;
    throw new Error('Case not found');
  }
  return get(`/api/v1/cases/${id}`);
}

export async function getCaseEvidence(id: string): Promise<CaseEvidence> {
  if (isMock) { await delay(); return mock.mockCaseEvidence; }
  return get(`/api/v1/cases/${id}/evidence`);
}

export async function verifyCase(id: string): Promise<VerifyResult> {
  if (isMock) { await delay(1500); return mock.mockVerifyResult; }
  return post(`/api/v1/cases/${id}/verify`);
}

export async function resetDemo(): Promise<{ ok: boolean; run_id: string }> {
  if (isMock) { await delay(1000); return { ok: true, run_id: 'RUN-20260929-130000' }; }
  return post('/api/v1/demo/reset');
}

export async function runDemo(step?: number): Promise<DemoStatus> {
  if (isMock) { await delay(2000); return mock.mockDemoStatus; }
  return post('/api/v1/demo/run', step ? { step } : {});
}

export async function getDemoStatus(): Promise<DemoStatus> {
  if (isMock) { await delay(); return mock.mockDemoStatus; }
  return get('/api/v1/demo/status');
}

export async function restoreGolden(): Promise<DemoStatus> {
  if (isMock) { await delay(1000); return { ...mock.mockDemoStatus, mode: 'golden' }; }
  return post('/api/v1/demo/restore-golden');
}
