"""T-SS-1 — scraper 3 passes Layer 2, is trapped by Layer 3 and harvests all five canaries. Master plan §6, §19."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ANCHORS = ("Oriel Vantrask", "Hexaquorum", "quasar-reconcile", "velvet-anchor", "ORCHID-7")
RESET_DEPS = ("sb.main", "sb.store.db", "sb.hooks", "sb.canary.seed", "sb.trap.layer3", "sb.provenance.dataset")
TRAP_ID = re.compile(r"TRAP-[A-Z0-9]+-[A-Z0-9]+")
EXPECTED_TRAPS = {"TRAP-ROBOTS-01", "TRAP-LINK-01"}


def trap_ids(obj) -> set[str]:
    return set(TRAP_ID.findall(json.dumps(obj)))


@pytest.mark.headed
@pytest.mark.requires(
    *RESET_DEPS, "sb.edge.pipeline", "sb.edge.layer1", "sb.edge.layer2", "sb.edge.intel", "sb.trap.injector",
)
def test_sophisticated_scraper_passes_l2_then_is_trapped(api, reset, attack, wait_for):
    dataset = REPO / "data" / "datasets" / f"{reset['run_id']}_scraper3.jsonl"
    out = attack("sophisticated_scraper.py", "--out", str(dataset), timeout=300)
    ua = out["user_agent"]

    events = sorted((e for e in api.events() if e["user_agent"] == ua), key=lambda e: e["seq"])
    pass_seqs = [e["seq"] for e in events if e["decision"] == "PASS"]
    trap_seqs = [e["seq"] for e in events if e["decision"] == "TRAP"]
    assert pass_seqs, f"scraper 3 never passed L2: {[(e['seq'], e['decision'], e['reasons']) for e in events]}"
    assert trap_seqs and min(pass_seqs) < min(trap_seqs), "expected PASS before TRAP"

    def matching_session():
        for summary in api.sessions():
            detail = api.session(summary["session_id"])
            if detail.get("user_agent") == ua and detail.get("classification") == "SOPHISTICATED_SCRAPER":
                return detail
        return None

    session = wait_for(
        matching_session,
        15,
        what="scraper 3 session classified SOPHISTICATED_SCRAPER",
    )
    detail = session
    assert detail.get("state") == "TRAPPED", detail.get("state")
    hit = trap_ids(detail) | trap_ids([e for e in events if e["decision"] == "TRAP"])
    assert hit & EXPECTED_TRAPS, f"trap ids seen: {sorted(hit)}"

    exposures = api.exposures()
    unexposed = sorted(cid for cid, rows in exposures.items() if not rows)
    assert len(exposures) == 5 and not unexposed, f"canaries without exposure: {unexposed}"

    records = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records, "empty dataset"
    for rec in records:
        assert set(rec) == {"url", "fetched_at", "title", "text"}, rec.keys()
    corpus = "\n".join(r["text"] for r in records)
    missing = [a for a in ANCHORS if a not in corpus]
    assert not missing, f"dataset lacks anchors {missing}"
