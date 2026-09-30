# Hackathon readiness and freeze

Starting main: `f79200145c7493fff4900b9c81788f14c75a85c5`. Latest merged phases: 8 harness (#33), 9 live dashboard (#34), 10 recovery (#35), 11 real provenance/evidence (#36). No history audit.

Accepted Phase 10/11 datasets, manifests, probe/case/session identities, frozen v2 canaries, model digest, contracts and evidence are preserved. Before resets, 53 data/evidence artifacts were hash-inventoried and backed up outside the worktree at `/home/rosso/scrapebuster-release-preserved-f792001`; local agent checkpoints moved there to establish a clean starting worktree. Rehearsal must use isolated runtime paths.

## Initial capability matrix

| Capability | State | Evidence | Action |
|---|---|---|---|
| CampusCart proxy | WORKING BUT UNVERIFIED — verify only | Phase 10/11 origin-derived captures | Current browser/routes/assets check |
| Human flow | WORKING BUT UNVERIFIED — verify only | Accepted VERIFIED/HUMAN_LIKELY, 5 pages, no exposures | Fresh browser + marked control |
| Layer 1 | WORKING BUT UNVERIFIED — verify only | Accepted 3 throttles/7 blocks, BOT_BASIC/BLOCKED | Fresh bounded client; no retuning |
| Layer 2 | WORKING BUT UNVERIFIED — verify only | Accepted AUTOMATION/RESTRICTED, zero content | Fresh existing client |
| Layer 3 | WORKING BUT UNVERIFIED — verify only | Accepted PASS→TRAP, five session-linked exposures | Fresh existing client |
| Canaries | WORKING — do not modify | Frozen five v2 IDs/hashes/anchors, registry tests | Preserve |
| Telemetry | WORKING BUT UNVERIFIED — verify only | Accepted 87 persisted events and snapshots | Same-run DB/API comparison |
| Sessions | WORKING BUT UNVERIFIED — verify only | Accepted four classes/states | Same-run DB/API comparison |
| Dashboard live API | WORKING BUT UNVERIFIED — verify only | Phase 9 client live-only, explicit stale/offline UI | Browser proof and Overview clarity |
| Real scraper dataset | WORKING — do not modify | Accepted 20-record target plus exact original Phase 10 backup | Preserve; fresh rehearsal is additional |
| Control dataset | WORKING — do not modify | 14 direct-origin records, Phase 7 hash, zero anchors | Reuse |
| RAG | WORKING — do not modify | Phase 11 real retrieval/probe references; unit coverage | Reuse canonical implementation |
| Doberman | WORKING BUT UNVERIFIED — verify only | Phase 11 all ten LIVE outputs, qwen2.5:3b/digest | Fresh intended-model execution |
| Correlation | WORKING — do not modify | Two exact detections suffice, control NO_SIGNAL, MEDIUM confidence | No thresholds/prompts tuning |
| Case creation | WORKING — do not modify | SB-001 linked to real run/session | Fresh API case check |
| Evidence | WORKING — do not modify | Accepted VALID and isolated-copy TAMPERED | Preserve; verify fresh bundle |
| Reset | BROKEN — minimally fix | Current reset deletes accepted data/datasets/*.jsonl and ingested copies | Isolate runtime dataset/evidence/golden paths |
| Demo runner | WORKING BUT UNVERIFIED — verify only | Basic client stops conservatively on edge 429; runner treats safety stop as failure | Exercise actual step; distinguish proven L1 enforcement without retry |
| Golden/replay | WORKING BUT UNVERIFIED — verify only | Golden implementation exists; no accepted golden snapshot yet | Capture once after full live success; restore verify |
| AWS | OPTIONAL / POST-HACKATHON — defer | No live cloud preservation acceptance | LOCAL EVIDENCE MODE |
| Dashboard dependencies | MISSING BUT DEMO-CRITICAL — implement minimally | make check reached dashboard then tsc not found | Existing npm ci, no dependency overhaul |
| Preflight health mapping | BROKEN — minimally fix | Health reports upstream/not_checked; script expects origin/ok | Honest mapping and direct dependency gates |

Baseline automated gate: backend unit 206 passed/1 skipped; contract 1 passed; Ruff scope and 19 fixtures passed. Dashboard gate stopped on missing installed dependencies, not a source compile failure. Independent Codex read-only reviews found no contradictions in historical security/provenance acceptance; fresh live execution remains necessary.

## Parallel-safe ownership

- DashboardReadiness: Overview.tsx and ApiStateNotice.tsx only; client adapter read-only; existing dashboard dependencies.
- ReleaseEnvironment: preflight, runtime path constants in demo/provenance, ignore rule and operator runbook only.
- Supervisor: runner cross-domain blocker and final live sequence, preservation, verification, integration, PR and freeze.
- Locked: main.py, config.py, contracts.py, Layer 1/2, pipeline.py, session security, trap behavior, canaries, schemas/fixtures and dashboard API adapter. No worker may edit these.

Managed launch receipts pin Gemini 3.7 Flash High. Turn-start acknowledgement was unconfirmed, but bounded terminal evidence shows both assignments executing; no launch repeated and reservations retained. Luna Medium remains control-only under installed policy. No automatic provider fallback.

## Integrated release fixes and exercised gates

- Isolated demo outputs, ingested copies, evidence and golden snapshots under `SB_RUNTIME_DIR` (default `data/runtime`). The control and canonical Phase 10/11 paths remain unchanged. Preflight uses the same path and the actual `upstream` health key; unprobed health components are warnings alongside direct origin/model checks.
- Kept attacker safety stops. The ordinary demo step accepts a stopped 403/429 batch only when persisted same-session L1 rows account for every response, the UA matches, content bodies are zero, and the state is BOT_BASIC/BLOCKED. Upstream 429/5xx or incomplete proof still fails with no retry. Five boundary cases cover this distinction.
- Added a real-API Overview summary; removed invented run/model/health/outcome fallbacks. Counts distinguish registered canaries from state transitions; control language is limited to this run; RAG reproduction is not described as proof of training. Evidence is unverified until the operator calls the verification API. Actual outage smoke exposed cached HEALTHY precedence; health now becomes UNAVAILABLE while data is explicitly STALE.
- Actual golden-after-reset smoke exposed missing ingested target/control files although evidence remained VALID. Golden now captures/restores both ingested datasets and the chain, refuses incomplete old snapshots, and never overwrites existing live evidence/chain. A regression exercises real retrieval from both restored datasets after reset.
- `make check`: 212 unit passed, 1 optional botocore/boto3 skip, 1 contract passed, 19 schema fixtures passed; dashboard typecheck and production build passed. Ownership checker emits its advisory warning for coordinator edits across owner boundaries. No owner approvals are claimed. Additional touched-file Ruff found an import spacing issue; corrected without formatter churn.
- Independent managed verifier: 22 integration passed; accepted Phase 11 original VALID and isolated-copy TAMPERED smoke passed. Dashboard existing suite: 4 passed. No contracts, fixtures, canary content, security thresholds, clients, RAG/Doberman/correlation logic or AWS resources changed.
- First fresh isolated rehearsal `RUN-20260930-040755`: seven CLI steps PASS, 88 API/DB-matching events, four classes/states, zero human trap hits/exposures, five scraper v2 exposures, 20-record target, unchanged 14-record control, ten LIVE intended-model outputs, MEDIUM two-canary target signal, negative controls, evidence VALID (22 checks), isolated copy TAMPERED. This capture is preserved externally; final-candidate golden validation follows the preservation repair.
