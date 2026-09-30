// All dashboard runtime reads and writes use the Phase 6 live backend API.
import type {
  Canary,
  CanaryDetail,
  Case,
  CaseEvidence,
  CaseSummary,
  Dataset,
  DemoResetResponse,
  DemoStatus,
  Health,
  Overview,
  ProbeRun,
  ProbeRunResponse,
  SessionDetail,
  SessionSummary,
  TrafficEventsResponse,
  VerifyResult,
} from '../types/contracts';

export const API_MODE = 'live' as const;

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(
    message: string,
    status: number,
    path: string,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });
  const body = await response.text();
  if (!response.ok) {
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') detail = parsed.detail;
    } catch {
      // Keep the response text for non-JSON proxy and server errors.
    }
    throw new ApiError(
      `${init?.method ?? 'GET'} ${path} failed (${response.status})${detail ? `: ${detail}` : ''}`,
      response.status,
      path,
    );
  }
  if (!body) return undefined as T;
  return JSON.parse(body) as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const getHealth = () => get<Health>('/api/v1/health');
export const getOverview = () => get<Overview>('/api/v1/overview');
export const getEvents = (after = 0) =>
  get<TrafficEventsResponse>(`/api/v1/traffic/events?after=${after}&limit=200`);
export const getSessions = () => get<{ sessions: SessionSummary[] }>('/api/v1/sessions');
export const getSession = (id: string) => get<SessionDetail>(`/api/v1/sessions/${encodeURIComponent(id)}`);
export const getCanaries = () => get<{ canaries: Canary[] }>('/api/v1/canaries');
export const getCanary = (id: string) => get<CanaryDetail>(`/api/v1/canaries/${encodeURIComponent(id)}`);
export const getDatasets = () => get<{ datasets: Dataset[] }>('/api/v1/datasets');
export const runProbe = (body: Record<string, unknown> = {}) =>
  post<ProbeRunResponse>('/api/v1/probes/run', body);
export const getProbes = () => get<{ probes: ProbeRun[] }>('/api/v1/probes');
export const getProbe = (id: string) => get<ProbeRun>(`/api/v1/probes/${encodeURIComponent(id)}`);
// Phase 6 deliberately defines the cases collection as a raw array.
export const getCases = () => get<CaseSummary[]>('/api/v1/cases');
export const getCase = (id: string) => get<Case>(`/api/v1/cases/${encodeURIComponent(id)}`);
export const getCaseEvidence = (id: string) =>
  get<CaseEvidence>(`/api/v1/cases/${encodeURIComponent(id)}/evidence`);
export const verifyCase = (id: string) =>
  post<VerifyResult>(`/api/v1/cases/${encodeURIComponent(id)}/verify`);
export const resetDemo = () => post<DemoResetResponse>('/api/v1/demo/reset');
export const runDemo = (step?: number) => post<DemoStatus>('/api/v1/demo/run', step ? { step } : {});
export const getDemoStatus = () => get<DemoStatus>('/api/v1/demo/status');
export const restoreGolden = () => post<DemoStatus>('/api/v1/demo/restore-golden');
