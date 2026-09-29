"""T-NU-1 — the human control passes Layer 2 and never sees a canary. Master plan §5, §6 honesty rule, §19."""
from __future__ import annotations

import pytest

RESET_DEPS = ("sb.main", "sb.store.db", "sb.hooks", "sb.canary.seed", "sb.trap.layer3", "sb.provenance.dataset")
BAD_CLASSES = {"BOT_BASIC", "AUTOMATION", "SOPHISTICATED_SCRAPER"}


@pytest.mark.headed
@pytest.mark.requires(*RESET_DEPS, "sb.edge.pipeline", "sb.edge.layer2", "sb.edge.intel", "sb.trap.injector")
def test_human_control_passes_and_gets_no_canaries(api, reset, attack, wait_for):
    out = attack("human_control.py")
    ua = out["user_agent"]

    assert out["content_pages"] >= 5, out["pages"]
    assert out["anchors_found"] == [], "canary served to a normal user"

    events = [e for e in api.events() if e["user_agent"] == ua]
    assert any(e["decision"] == "PASS" for e in events), [e["decision"] for e in events]
    assert not [e for e in events if e["decision"] in ("TRAP", "RESTRICT", "BLOCK", "THROTTLE")], events

    classes = wait_for(
        lambda: (c := {s.get("classification") for s in api.sessions() if s.get("user_agent") == ua})
        and "HUMAN_LIKELY" in c and c,
        10, what="human session classified HUMAN_LIKELY",
    )
    assert not classes & BAD_CLASSES, classes

    exposures = api.exposures()
    assert sum(len(v) for v in exposures.values()) == 0, exposures
    assert {c["status"] for c in api.canaries()} == {"ACTIVE"}
