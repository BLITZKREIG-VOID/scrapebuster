"""T-E2E-1 — reset, then all 7 runner steps PASS, case DETECTED, evidence VALID. Master plan §20."""
from __future__ import annotations

import os

import pytest

RESET_DEPS = ("sb.main", "sb.store.db", "sb.hooks", "sb.canary.seed", "sb.trap.layer3", "sb.provenance.dataset")
ALL_DEPS = (
    *RESET_DEPS, "sb.edge.pipeline", "sb.edge.layer1", "sb.edge.layer2", "sb.edge.intel", "sb.trap.injector",
    "sb.provenance.doberman", "sb.provenance.correlate", "sb.provenance.evidence",
)
RUN_BUDGET_S = (30 + 60 + 120 + 20 + 120 + 10 + 10) * 2 + 60  # every step retried once, plus margin
HEADLESS = os.environ.get("SB_DEMO_HEADLESS", "").lower() in ("1", "true", "yes")


def items(payload, key: str) -> list:
    return payload[key] if isinstance(payload, dict) else payload


@pytest.mark.requires(*ALL_DEPS)
@(pytest.mark.browser if HEADLESS else pytest.mark.headed)
def test_full_demo_all_steps_pass(api, reset, wait_for):
    started = api.post("/api/v1/demo/run", {})
    assert started["phase"] == "RUNNING" and started["run_id"] == reset["run_id"]

    status = wait_for(
        lambda: (s := api.get("/api/v1/demo/status"))["phase"] != "RUNNING" and s,
        RUN_BUDGET_S, what="demo run to finish",
    )
    summary = [(s["id"], s["name"], s["status"], s["detail"]) for s in status["steps"]]
    assert [s["status"] for s in status["steps"]] == ["PASS"] * 7, summary
    assert status["phase"] == "COMPLETE" and status["mode"] == "live"

    cases = items(api.get("/api/v1/cases"), "cases")
    latest = max(cases, key=lambda c: c.get("created_at") or "")
    assert latest["status"] == "PROVENANCE_SIGNAL_DETECTED", latest

    verify = api.post(f"/api/v1/cases/{latest['case_id']}/verify")
    assert verify["result"] == "VALID", [c for c in verify.get("checks", []) if not c.get("ok")]
