"""T-NU-1 — the human control passes Layer 2 and never sees a canary. Master plan §5, §6 honesty rule, §19."""
from __future__ import annotations

import pytest

RESET_DEPS = ("sb.main", "sb.store.db", "sb.hooks", "sb.canary.seed", "sb.trap.layer3", "sb.provenance.dataset")
BAD_CLASSES = {"BOT_BASIC", "AUTOMATION", "SOPHISTICATED_SCRAPER"}


@pytest.mark.headed
@pytest.mark.requires(*RESET_DEPS, "sb.edge.pipeline", "sb.edge.layer2", "sb.edge.intel", "sb.trap.injector")
def test_human_control_passes_and_gets_no_canaries(api, reset, attack, wait_for, site):
    out = attack("human_control.py", "--site", site)
    ua = out["user_agent"]

    assert out["content_pages"] >= 5, out["pages"]
    assert out["anchors_found"] == [], "canary served to a normal user"

    events = [e for e in api.events() if e["user_agent"] == ua]
    assert any(e["decision"] == "PASS" for e in events), [e["decision"] for e in events]
    assert not [e for e in events if e["decision"] in ("TRAP", "RESTRICT", "BLOCK", "THROTTLE")], events

    def matching_human_sessions():
        return [
            detail for summary in api.sessions()
            if (detail := api.session(summary["session_id"])).get("user_agent") == ua
        ]

    human_sessions = wait_for(
        matching_human_sessions,
        10,
        what="human detailed session recorded",
    )
    classes = {session.get("classification") for session in human_sessions}
    assert "HUMAN_LIKELY" in classes, human_sessions
    assert not classes & BAD_CLASSES, classes

    exposures = api.exposures()
    assert sum(len(v) for v in exposures.values()) == 0, exposures
    assert {c["status"] for c in api.canaries()} == {"ACTIVE"}
