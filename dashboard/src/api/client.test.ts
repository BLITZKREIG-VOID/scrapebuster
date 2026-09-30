import { afterEach, describe, expect, it, vi } from 'vitest';
import { API_MODE, ApiError, getCases, getOverview, getHealth } from './client';

afterEach(() => vi.unstubAllGlobals());

describe('live backend API client', () => {
  it('uses live mode at runtime', () => {
    expect(API_MODE).toBe('live');
  });

  it('preserves the raw-array cases response from the frozen Phase 6 contract', async () => {
    const cases = [{
      case_id: 'CASE-LIVE-001',
      run_id: 'RUN-LIVE-001',
      created_at: '2026-09-30T10:00:00Z',
      status: 'PROVENANCE_SIGNAL_DETECTED',
      confidence: 'HIGH',
      primary_canary_id: 'CANARY-LIVE-001',
    }];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(cases), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getCases()).resolves.toEqual(cases);
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/cases', expect.any(Object));
  });

  it('returns persisted health and overview responses without fixture substitution', async () => {
    const health = { status: 'ok', components: { db: 'ok', upstream: 'not_checked' } };
    const overview = {
      run_id: 'RUN-LIVE-001',
      counts: { ALLOW: 0, ESCALATE: 0, CHALLENGE: 0, PASS: 0, RESTRICT: 0, THROTTLE: 0, BLOCK: 0, TRAP: 0 },
      ladder: { safe: 0, suspicious: 0, challenge_restrict: 0, block: 0, trap: 0, provenance: 0 },
      sessions_by_class: {}, canaries: { active: 0, exposed: 0, observed: 0 }, cases: { total: 0, detected: 0 },
      pipeline: [], latest_case: null,
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(overview), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getHealth()).resolves.toEqual(health);
    await expect(getOverview()).resolves.toEqual(overview);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/v1/health', '/api/v1/overview']);
  });

  it('surfaces HTTP errors instead of returning dashboard fixture data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'database offline' }), { status: 503 })));

    await expect(getOverview()).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'GET /api/v1/overview failed (503): database offline',
    } satisfies Partial<ApiError>);
  });
});
