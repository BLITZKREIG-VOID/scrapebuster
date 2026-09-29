# Architectural Decisions

| Date | Decision | Rationale | Owner |
|---|---|---|---|
| 2026-09-29 | Product Name is "ScapeBusters" in UI, code prefix `sb` | Resolves conflict between brief and pitch deck. | Anirudh |
| 2026-09-29 | Edge Spine (Proxy, L1, L2, Store) built by Anirudh | Builder ≠ Validator (Arnav builds attacks/demo site). | Team |
| 2026-09-29 | Local Model via Ollama (`qwen2.5:3b`) | Fully offline-capable demo on one laptop. | Team |
| 2026-09-30 | **OD-3 (b), Phase 7 freeze:** five synthetic CampusCart marketplace canaries at v2, replacing v1. IDs and anchors are retained; canonical hashes change. | Final real scraper generation waits for this phase's merge. Old v1 target datasets/replays are not final-run inputs. See `PHASE_07_HARDIK_CANARIES_CONTROL.md` and `data/canary_manifest.json`; direct-origin control has zero anchors. | HARDIK / Rossonerian |
| 2026-09-29 | **OD-4 (a):** on CampusCart, canaries reach scrapers only through the trap decoys. For a TRAPPED session, the `/internal/*` robots decoy (TRAP-ROBOTS-01) carries every non-DRAFT canary with one exposure per canary, and the decoy API still carries SB-CAN-0003. Hydrated SPA pages are not injected. | CampusCart is a client-rendered SPA with no `</main>` placement pages. The `</main>` placement injection stays for the local ExampleCorp test origin, but it cannot fire on CampusCart. Untrapped sessions and the hidden legacy index never receive canaries. The pitch states plainly that delivery happens via the trap. Ported by Hardik (owner of `sb/trap/injector.py`) from closed PR #8. | Hardik + Arnav |
| 2026-09-30 | **Probe separation:** CampusCart v2 prompts contain no registered anchor or context term across all five canaries. | Shared ordinary subject words support top-1 controlled-fixture retrieval without leaking the answer. The prior SB-CAN-0004 overlap failure remains resolved without xfail. | HARDIK / Rossonerian |
