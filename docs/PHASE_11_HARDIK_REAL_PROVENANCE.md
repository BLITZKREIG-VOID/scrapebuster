# Phase 11 — HARDIK / Rossonerian

## Preimplementation plan and dependency gate

Phase 6/7/10 merges are ancestors of main `8f0db2f9ac8f6424d312eb83d669b1146b020eb3`. PR #35 is a recovery handoff, not completed Phase 10 acceptance. Its supplied real target and exact backup both hash to `8dd0ecaf1ab00171709dc5dcbb80507159b8d6a55c59cd848d2f0932764220f4`. The committed manifest/raw snapshots belong to the lost earlier run, not this target. Local runtime DB has no sessions, exposures or trap hits, and no edge service is running. Do not invent or relabel those missing rows.

1. Recover Phase 10 acceptance first: execute the unchanged bounded human/basic/advanced/sophisticated clients against a dedicated loopback edge backed only by CampusCart. Capture exact target bytes, all raw API rows and run/session metadata before any tests/reset. Validate zero human exposures, blocked/restricted outcomes, L2→L3 transitions, all five exposure/session links, and frozen v2 hashes. Preserve original Phase 10 artifacts. New run identity is mandatory. No security/attack patches.
2. Verify the clean control is non-empty, direct-origin and contains no registered anchors. Record target/control checksums and counts in a run-scoped handoff. Stop Phase 11 if the recovery cannot establish the real chain.
3. Register accepted real target and control through canonical dataset ingestion, preserving exact bytes. Dataset contracts have no run/session fields: capture association in execution/evidence metadata without contract changes. Ingestion builds canonical target/control RAG indexes; use only actual scraped text.
4. Invoke actual Doberman/investigation path. Prefer installed local Ollama model configured through SB_LLM_MODEL, not a wrapper change; capture model name/digest and per-result mode, probe/output IDs. Label fallback honestly; never use replay.
5. Apply existing exact-anchor, context, uniqueness, timing and integrity criteria unchanged. Target must yield PROVENANCE_SIGNAL_DETECTED, control NO_SIGNAL. Unexpected misses are defects, not a reason to lower thresholds; Phase 16 owns tuning.
6. Preserve real publication, trap-hit, exposure and session rows from recovery in the same runtime DB for investigation. Verify case links and dataset/probe chain. Generate canonical local bundle with mandatory non-overclaim statement, hashes and previous-chain linkage.
7. Verify bundle through canonical verifier/API. Exercise tamper detection on an isolated copy only; never mutate accepted evidence. Run provenance/RAG/correlation/evidence/API tests separately from recovery runtime state, plus real-data execution.
8. Commit compact metadata/evidence interfaces and accepted evidence; create one PR. Merge only after required checks pass. Checkout latest main, verify merge SHA, run lightweight persisted-evidence smoke, and post final PR comment. Do not start Phase 12.

## Failure ownership

- Phase 10 missing snapshots: recover with a new bounded run; never manufacture exposure rows.
- Edge/security/health API issues: ANI owns implementation; no Layer 1/2 or API-contract edits here. The handoff notes origin/upstream naming mismatch; use live health/API evidence, not preflight assumptions.
- Provenance ingestion/RAG/Doberman/correlation/evidence defects: HARDIK, minimal fix only when real execution blocks acceptance.
- Ollama availability/configuration: start local service and use observed inventory; no automatic model/provider fallback. Wrapper extractive fallback remains explicitly labelled if encountered.
- AWS/dashboard: out of scope and unverified.

## Executed recovery and acceptance

The first new run, `RUN-20260930-023742`, was rejected: an unseeded fresh runtime had no canaries and the sequential ordinary bot stopped on its first throttle. Its artifacts are not provenance inputs. Changed approach: seed the frozen registry before requests, use a fresh dedicated DB/edge, and execute the unchanged ordinary client with one ten-request concurrent batch. No security-layer changes or safety-stop bypass.

Accepted recovery: **RUN-20260930-024139**, executed main SHA `8f0db2f9ac8f6424d312eb83d669b1146b020eb3`. `data/manifest_RUN-20260930-024139.json` preserves session IDs, timestamps, exact dataset hash/count, commits, publication/exposure/session/trap/traffic snapshots and their checksums. The old Phase 10 dataset and backup remain unchanged; historical rows were not relabelled. Snapshot totals: 4 sessions, 87 traffic events, 2 trap hits, 5 exposures, 5 publications.

Executed commands (Python executable `/tmp/sb-venv/bin/python`):

```text
attacks/human_control.py --base http://127.0.0.1:8002 --pages 5 --screenshot data/evidence/RUN-20260930-024139/human_rendered_campuscart.png
attacks/ordinary_bot.py --base http://127.0.0.1:8002 --requests 10 --threads 10
attacks/advanced_scraper.py --base http://127.0.0.1:8002 --pages 5
attacks/sophisticated_scraper.py --base http://127.0.0.1:8002 --out data/datasets/RUN-20260930-024139_scraper3.jsonl
```

Human: 5/5 content pages, VERIFIED/HUMAN_LIKELY, zero anchors/traps/exposures. Basic: 3 throttles/7 blocks, final BLOCKED, zero protected bodies, safety-stop exit 3 after the single concurrent batch. Advanced: RESTRICTED, zero protected pages. Sophisticated: 20 real records, all five anchors, L2 PASS then L3 TRAP, session `ck-4489f36ec6963a87`. Human control is seeded browser simulation, not manual human traffic.

## Real provenance execution

- Target: `DS-fbbf25a6`, 20 records, SHA-256 `2c46ecbbc24a1fc78557286ae9deea347f6ab8249f141ad130a9c3eb571e7301`.
- Control: `DS-fad6f09f`, 14 direct-origin records, SHA-256 `db149b52de047c9f635a2983166645cf37b3191770b3a57220bbf945086ba151`; zero registered anchors.
- Actual HTTP POST `/api/v1/datasets/ingest` for target/control followed by `/api/v1/probes/run` with those IDs. Ingestion built canonical BM25 indexes; no manual canary context was added.
- Target probe: `PRB-fc1bb6e7`; control probe: `PRB-ae27606f`. Both DONE, all ten outputs LIVE.
- Model: `qwen2.5:3b`, digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`. The actual local inventory differs from the earlier Phase 10 handoff's machine: this model is installed. Empty-prompt warmup loaded it before probes. No fallback or replay.
- Probe/output IDs, actual questions, retrieval chunk IDs/scores, response hashes and modes are preserved in the run-scoped probe snapshots and canonical evidence.
- Case: `SB-001`, run/session linked, target `PROVENANCE_SIGNAL_DETECTED`, control `NO_SIGNAL` verified using canonical correlation on actual control responses.
- Detected: SB-CAN-0002 and SB-CAN-0003. SB-CAN-0001/0004/0005 returned NO_SIGNAL: LIVE output omitted their registered anchors. Recorded retrieval/generation misses; no canary, prompt, retrieval or correlation-threshold changes. Phase 16 owns stability work.
- Canonical statement now explicitly excludes theft, intent, authorship, operator identity and legal causation. Removed obsolete exact-wording tests instead of repinning them.

## Local evidence and verification

Bundle: `evidence/RUN-20260930-024139/SB-001/` (nine canonical payloads plus manifest). Chain: `evidence/chain.json`; first bundle links to the supported zero-hash genesis.

- Manifest canonical self-hash: `f3fa67a799a2d3a0a3efcbc9f2ef9fefb2d62493509e7cbbbf129b261275e950`.
- Manifest file-byte hash: `e3e35bc2916489bc1bf9dcd0ac1d9c3909f56e9262eea9cec5741497d5f3c6e8`.
- GET `/api/v1/cases/SB-001/evidence` succeeded; POST `/api/v1/cases/SB-001/verify` returned VALID, including disk/DB object hashes and chain checks.
- Isolated copy of `06_model_response.json` modified: canonical verification returned TAMPERED. Original production evidence reverified VALID.
- `data/phase11_handoff.json` is the compact Phase 12 interface. Dataset API contracts lack run/session fields; association is captured in this handoff and canonical case/evidence, not invented contract fields.

## Verification commands and observed outputs

```text
PYTHONPATH=backend /tmp/sb-venv/bin/python -m pytest backend/tests/unit/provenance backend/tests/contract/test_api_contracts.py backend/tests/integration/test_api_runtime_surface.py -q -p no:cacheprovider
59 passed, 1 skipped, 1 warning in 3.03s

/tmp/sb-venv/bin/python scripts/verify_phase11_handoff.py --tamper-copy
{"case_id": "SB-001", "control": "NO_SIGNAL", "run_id": "RUN-20260930-024139", "tamper_copy": "TAMPERED", "target": "PROVENANCE_SIGNAL_DETECTED", "verify": "VALID"}

PYTHONPATH=backend /tmp/sb-venv/bin/python -m pytest backend/tests/unit backend/tests/contract backend/tests/integration scripts/tests -q -p no:cacheprovider
259 passed, 1 skipped, 2 warnings, 2 subtests passed in 8.16s

/tmp/sb-venv/bin/python -m ruff check backend/sb/main.py backend/sb/contracts.py backend/sb/store backend/sb/edge backend/sb/api scripts/check_contracts.py scripts/export_schemas.py
All checks passed!

/tmp/sb-venv/bin/python scripts/check_contracts.py
19 response fixtures passed
```

Skip: optional real-botocore test without boto3. Warnings: dependency deprecations. Persisted evidence smoke recomputes actual correlations and canonical bundle checks; it does not claim a new LIVE probe run.

## Phase 12 handoff and limits

Preserve the accepted bundle, chain, raw attack snapshots, target and control before S3 work. Local evidence interface and API verification are validated; AWS/S3 live preservation, dashboard E2E, repeated model-run stability and a managed Gemini verifier remain unverified. The previously exhausted managed-worker attempts were not retried. No Phase 12 implementation has started.

OWNER: HARDIK / Rossonerian  
COMPLETED PHASES: 2 / 5  
REMAINING OWNER PHASES: 3 / 5

- P12 S3 preservation implementation
- P14 S3 live acceptance
- P16 Provenance stability/replay

CURRENT HANDOFF: Validated local evidence interface + real evidence bundle → HARDIK Phase 12.

## Reset-test blocker resolved

The integration ordinary-bot fixture reused a healthy external edge and called `/demo/reset`, deleting repository datasets during the combined suite. The accepted target bytes and consumed ingestion copies were restored from the exact in-memory execution capture, with checksum unchanged; the committed original Phase 10 target was restored unchanged. A byte-exact recovery backup is now preserved under the accepted run's evidence directory.

`backend/tests/integration/test_l1_ordinary_bot.py` now always starts its own edge on an ephemeral loopback port, with a scratch DB and scratch reset dataset directory. It never resets an operator's running edge. No Layer 1/2, attack, contract or production reset changes.

Final combined suite after fixture isolation: **259 passed, 1 skipped, 2 warnings, 2 subtests passed in 10.18s**. Immediately afterward, real-data smoke returned target PROVENANCE_SIGNAL_DETECTED, control NO_SIGNAL, evidence VALID, isolated-copy TAMPERED; SHA-256 checks confirmed both real target captures and the registered target copy survived unchanged.
