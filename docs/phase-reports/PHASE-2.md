# Phase 2 — Adaptive AR Classifier and Dynamic Router

**Report Date:** 2026-10-10  
**Branch:** `phase2-implementation` (baseline `329a758`)  
**Integration Owner:** Supervisor  
**Implementation Owner:** Phase 2 worker (recovered)  
**Independent Verifier:** `@verifier` (pending)

---

## 1. Scope Delivered, Owners, and Commit Range

### Commits
- Baseline: `329a758` (Phase 1 integration commit)
- Working tree: `phase2-implementation` branch with uncommitted changes
- Files modified: 27 tracked files, 12 untracked implementation/test files

### Implementation Ownership
- **Core classifier/router**: `backend/sb/classifier/`, `backend/sb/router/`
- **Pipeline integration**: `backend/sb/edge/pipeline.py`, `backend/sb/edge/session.py`
- **Configuration**: `backend/sb/config.py`, `.env.example`
- **API contracts**: `backend/sb/api/classifier.py`, `backend/sb/api/sessions.py`
- **Dashboard**: `dashboard/src/pages/Overview.tsx`, types and client
- **Tests**: Unit (12), Integration (5 new), Contract (existing)

---

## 2. Exit Criteria Mapped to Commands and Evidence

| Requirement (PRD FR) | Implementation | Verification Command | Status |
|---|---|---|---|
| FR-2.1 Per-route EMA baseline | `ARClassifier.record_sample()`, `update_route_baseline()` | `python -m pytest tests/unit/classifier/test_classifier.py::test_ema_baseline_formula -v` | ✅ PASS |
| FR-2.2 Trust score 0-100 | `classify_session()` computes trust_score | `python -m pytest tests/unit/classifier/test_classifier.py::test_matured_baseline_browser_fast_path -v` | ✅ PASS |
| FR-2.3 FAST_PATH zero mutation | Pipeline bypasses mutation when `decision == "FAST_PATH"` | `python -m pytest tests/integration/test_phase2_ar_classifier_router.py::test_genuine_browser_cascade_fast_path_and_byte_identity -v` | ✅ PASS |
| FR-2.4 Sticky sandbox lock (20 API calls) | `ar_anomaly_streak >= 20` sets `locked_sandbox=True` | `python -m pytest tests/integration/test_phase2_ar_classifier_router.py::test_scraper_reconnaissance_triggers_sticky_sandbox_lock -v` | ✅ PASS |
| FR-2.5 Durability across restart | SQLite persistence for route_baselines, sessions | `python -m pytest tests/integration/test_phase2_ar_classifier_router.py::test_durability_across_proxy_restart -v` | ✅ PASS |
| FR-2.6 Cold start fail-offensive | Immature baseline (`sample_count < 10`) routes to SANDBOX | `python -m pytest tests/unit/classifier/test_classifier.py::test_cold_start_fails_offensive -v` | ✅ PASS |
| SB_MUTATION_MODE=adaptive\|always | Configurable via env, default adaptive | `python -m pytest tests/unit/classifier/test_classifier.py::test_mutation_mode_always_forces_sandbox -v` | ✅ PASS |
| Classifier status API | `/api/v1/classifier/status` endpoint | `python -m pytest tests/integration/test_phase2_ar_classifier_router.py::test_classifier_status_endpoint -v` | ✅ PASS |
| Dashboard route baseline view | Overview.tsx shows route table with AR EMA, maturity | Manual inspection | ✅ IMPLEMENTED |
| Forensic ledger integrity | `ledger.verify_chain()` returns VALID | `python -m pytest tests/integration/test_phase2_ar_classifier_router.py::test_forensic_ledger_integrity_after_mixed_traffic -v` | ✅ PASS |
| Router evaluation p95 < 2ms | Direct measurement in benchmark | Benchmark: 0.044ms p95 | ✅ PASS |
| Fast path added p95 < 5ms | Full proxy benchmark | Benchmark: 250ms p95 added | ❌ FAIL |
| Sandbox p95 < 50ms | Full proxy benchmark | Benchmark: 244ms p95 | ❌ FAIL |
| 500 req/s concurrent workload | Benchmark harness target | Not achieved (sequential only) | ❌ INCOMPLETE |

---

## 3. Test and Verification Results

### Unit Tests (12/12 PASS)
```
tests/unit/classifier/test_classifier.py::test_ema_baseline_formula PASSED
tests/unit/classifier/test_classifier.py::test_cold_start_fails_offensive PASSED
tests/unit/classifier/test_classifier.py::test_matured_baseline_browser_fast_path PASSED
tests/unit/classifier/test_classifier.py::test_matured_baseline_scraper_divergence_sandbox PASSED
tests/unit/classifier/test_classifier.py::test_anomaly_streak_triggers_sticky_sandbox_lock PASSED
tests/unit/classifier/test_classifier.py::test_mutation_mode_always_forces_sandbox PASSED
tests/unit/classifier/test_classifier.py::test_classifier_status_and_metrics PASSED
tests/unit/router/test_router.py::test_route_normalization PASSED
tests/unit/router/test_router.py::test_router_evaluates_cold_start_to_sandbox PASSED
tests/unit/router/test_router.py::test_router_evaluates_trusted_browser_to_fast_path PASSED
tests/unit/router/test_router.py::test_router_fail_offensive_on_classifier_exception PASSED
tests/unit/router/test_router.py::test_audit_trail_fifo_capacity PASSED
```

### Contract Tests (37/37 PASS)
All existing Phase 0 and Phase 1 contract tests pass.

### Integration Tests (40/40 PASS)
```
tests/integration/test_proxy.py::test_proxy_flow PASSED (fixed)
tests/integration/test_phase2_ar_classifier_router.py::test_genuine_browser_cascade_fast_path_and_byte_identity PASSED
tests/integration/test_phase2_ar_classifier_router.py::test_scraper_reconnaissance_triggers_sticky_sandbox_lock PASSED
tests/integration/test_phase2_ar_classifier_router.py::test_durability_across_proxy_restart PASSED
tests/integration/test_phase2_ar_classifier_router.py::test_classifier_status_endpoint PASSED
tests/integration/test_phase2_ar_classifier_router.py::test_forensic_ledger_integrity_after_mixed_traffic PASSED
... + 34 Phase 0/1 regression tests
```

### Lint & Gates
```
ruff check backend/sb scripts: PASS
scripts/grep_gate.py: PASS (zero forbidden tokens)
scripts/check_contracts.py: PASS (19 fixtures validated)
scripts/check_dashboard.py: TypeScript typecheck + build PASS
```

---

## 4. Benchmark Results (Evidence: `phase2-evidence/router_benchmark.json`)

**Latest run (telemetry contention resolved, optimized):**
```
Router evaluation overhead: p50=0.031ms, p95=0.051ms, p99=0.108ms (target: p95 < 2ms) ✅ PASS
Raw origin end-to-end:     p50=1.5ms, p95=2.1ms
Proxy FAST_PATH end-to-end: p50=8.7ms, p95=14.3ms (added p95 = 12.2ms, target < 5ms) ❌ FAIL
Proxy SANDBOX end-to-end:   p50=3.8ms, p95=4.8ms (target: p95 < 50ms) ✅ PASS
```

**Previous run (telemetry contention resolved):**
```
Router evaluation overhead: p50=0.030ms, p95=0.044ms, p99=0.068ms (target: p95 < 2ms) ✅ PASS
Raw origin end-to-end:     p50=5.6ms, p95=7.1ms
Proxy FAST_PATH end-to-end: p50=34.0ms, p95=41.5ms (added p95 = 34.4ms, target < 5ms) ❌ FAIL
Proxy SANDBOX end-to-end:   p50=17.8ms, p95=30.5ms (target: p95 < 50ms) ✅ PASS
```

**Initial run (with telemetry contention):**
```
Router evaluation overhead: p50=0.030ms, p95=0.044ms, p99=0.068ms (target: p95 < 2ms) ✅ PASS
Raw origin end-to-end:     p50=2.5ms, p95=8.3ms
Proxy FAST_PATH end-to-end: p50=141ms, p95=259ms (added p95 = 250ms, target < 5ms) ❌ FAIL
Proxy SANDBOX end-to-end:   p50=210ms, p95=244ms (target: p95 < 50ms) ❌ FAIL
```

The sandbox path now passes NFR after resolving telemetry tap database contention. The fast path added latency remains above target due to proxy stack overhead (ASGI transport, pipeline, router evaluation) even without mutation.

### Benchmark Limitations (Known Gaps)
1. **Sequential execution only** — Benchmark runs requests sequentially, not at 500 req/s concurrent. No load generator for sustained concurrency.
2. **No organic asset cascades** — Fast path test uses pre-matured baseline but session asset ratio not built through real browser-like cascades (HTML + static assets).
3. **Measurement methodology** — "Added latency" computed as `proxy_p95 - origin_p95` (percentile subtraction), which PRD explicitly rejects as "not proof."
4. **Mutation latency bottleneck** — Sandbox path ~180-200ms mutation overhead from canary registry database operations (3+ sequential transactions per mutation).
5. **ASGITransport vs real server** — Benchmark uses in-process ASGITransport; real uvicorn server shows similar latency (~250ms).

---

## 5. PRD Deviations and Documented Decisions

| Deviation | Rationale | Mitigation |
|---|---|---|
| Fast path added latency 250ms vs 5ms target | Mutation path bottleneck affects sandbox; fast path skips mutation but still shows high latency due to proxy stack overhead | Requires optimization: batch ledger writes, connection pooling, async DB |
| Sandbox latency 244ms vs 50ms target | Deterministic fallback does 3+ sequential SQLite transactions per mutation (bind, expose, inject) | Batch canary binding/exposure/injection in single transaction |
| No 500 req/s concurrent benchmark | Benchmark harness is sequential; no async load generator implemented | Defer to Phase 2 completion: implement proper load test |
| No organic asset cascades in benchmark | Session asset ratio requires static asset requests; benchmark only hits HTML endpoints | Add static asset simulation to benchmark warmup |
| Percentile subtraction for added latency | PRD requires "defensible overhead measurement" | Implement paired-request measurement or fixed-origin comparison |

### Documented Decisions
1. **Baseline maturity threshold**: `SB_BASELINE_MIN_SAMPLES=10` (configurable). Conservative default ensures cold-start fail-offensive.
2. **Anomaly streak threshold**: `SB_AR_ANOMALY_STREAK=20` consecutive zero-AR API calls triggers sticky sandbox lock (per PRD default).
3. **Trust threshold**: `SB_TRUST_THRESHOLD=70.0` for FAST_PATH (per PRD).
4. **EMA alpha**: `SB_AR_ALPHA=0.2` (per PRD).
5. **Redis fallback**: `SB_REDIS_URL` configurable; defaults to embedded SQLite (implemented in `backend/sb/classifier/store.py`).
6. **Classifier failure mode**: Fail-offensive to SANDBOX with visible fault record in ledger (`router_fault_fallback` / `CLASSIFIER_EXCEPTION_FAIL_OFFENSIVE`).

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Benchmark NFR failure blocks Phase 3 | HIGH | Phase gate not passed | Optimize mutation path (batch ledger writes), implement proper 500 req/s load test |
| Mutation latency affects production | HIGH | Sandbox path too slow for real traffic | Batch canary registry operations; consider async mutation with response streaming |
| SQLite contention under load | MEDIUM | TelemetryTap + classifier + mutation all hit same DB | WAL mode + NORMAL synchronous; consider separate DB connections or Redis |
| Session trust score drift | LOW | Long-lived sessions may accumulate stale state | Session TTL / periodic re-evaluation (not yet implemented) |
| Dashboard route baseline staleness | LOW | In-memory cache refreshed from DB on each status call | Current implementation reloads from DB; acceptable |

---

## 7. Next-Phase Readiness and Blockers

### Ready for Phase 3 (Watermark Matrix & RAG)
- ✅ Core classifier/router logic complete and tested
- ✅ FAST_PATH / SANDBOX routing decisions functional
- ✅ Session trust score, anomaly streak, sticky lock working
- ✅ Durability across restarts verified
- ✅ API contracts and dashboard views implemented

### Blockers for Phase 2 Acceptance
1. **Benchmark NFR failure** — Fast path added p95 (34ms) exceeds 5ms target; sandbox now passes (30.5ms < 50ms)
2. **Missing 500 req/s concurrent benchmark** — No sustained load test implemented
3. **Missing organic asset cascade proof** — Fast path not exercised with genuine browser-like traffic
4. **Measurement methodology** — Percentile subtraction not defensible per PRD

### Required for Phase 2 Gate Closure
- [ ] Fix mutation latency (target: sandbox <50ms p95)
- [ ] Implement proper 500 req/s concurrent benchmark with organic cascades
- [ ] Implement defensible overhead measurement (paired requests or fixed-origin delta)
- [ ] Pass benchmark NFR targets
- [ ] Independent `@verifier` inspection of exact worktree and evidence
- [ ] File final `docs/phase-reports/PHASE-2.md` with acceptance

---

## Appendix: Evidence Manifest

| File | Description |
|---|---|
| `phase2-evidence/router_benchmark.json` | Benchmark results (failed NFR) |
| `backend/tests/unit/classifier/test_classifier.py` | 7 unit tests |
| `backend/tests/unit/router/test_router.py` | 5 unit tests |
| `backend/tests/integration/test_phase2_ar_classifier_router.py` | 5 integration tests |
| `backend/sb/classifier/classifier.py` | ARClassifier implementation |
| `backend/sb/classifier/store.py` | SQLite/Redis baseline persistence |
| `backend/sb/router/router.py` | DynamicRouter implementation |
| `backend/sb/edge/pipeline.py` | FAST_PATH/SANDBOX routing integration |
| `backend/sb/edge/session.py` | Session trust score, anomaly streak, lock |
| `backend/sb/api/classifier.py` | Classifier status endpoint |
| `dashboard/src/pages/Overview.tsx` | Route baseline dashboard view |
| `.env.example` | All Phase 2 config documented |