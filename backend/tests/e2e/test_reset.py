"""T-RS-1 — reset twice gives an identical clean state; evidence is never touched. Master plan §21."""
from __future__ import annotations

import hashlib
import re
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = REPO / "evidence"
DATASETS = REPO / "data" / "datasets"
RESET_DEPS = ("sb.main", "sb.store.db", "sb.hooks", "sb.canary.seed", "sb.trap.layer3", "sb.provenance.dataset")
RUN_ID = re.compile(r"^RUN-\d{8}-\d{6}$")


def snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def items(payload, key: str) -> list:
    return payload[key] if isinstance(payload, dict) else payload


@pytest.mark.requires(*RESET_DEPS, "sb.edge.pipeline", "sb.provenance.evidence")
def test_reset_twice_gives_clean_identical_state(api):
    evidence_before = snapshot(EVIDENCE)

    first = api.post("/api/v1/demo/reset", timeout=60)
    second = api.post("/api/v1/demo/reset", timeout=60)
    for result in (first, second):
        assert result["ok"], [c for c in result["checks"] if not c["ok"]]
        assert RUN_ID.match(result["run_id"]), result["run_id"]
    assert first["run_id"] != second["run_id"]

    assert api.events() == []
    assert api.sessions() == []
    assert items(api.get("/api/v1/cases"), "cases") == []
    assert items(api.get("/api/v1/datasets"), "datasets") == []
    canaries = api.canaries()
    assert len(canaries) == 5 and {c["status"] for c in canaries} == {"ACTIVE"}, canaries
    assert all(v == 0 for v in api.get("/api/v1/overview")["counts"].values())
    assert not list(DATASETS.glob("*.jsonl"))

    status = api.get("/api/v1/demo/status")
    assert status["run_id"] == second["run_id"] and status["mode"] == "live"
    assert {s["status"] for s in status["steps"]} == {"PENDING"}

    assert snapshot(EVIDENCE) == evidence_before, "reset modified evidence/"


def test_reset_fails_named_check_when_hook_missing(monkeypatch, tmp_path):
    """A missing subsystem reset hook is a named failed check, never a silent skip."""
    backend = str(REPO / "backend")
    if backend not in sys.path:
        monkeypatch.syspath_prepend(backend)
    monkeypatch.setenv("SB_DB_PATH", str(tmp_path / "sb.db"))
    calls: list[str] = []

    def module(name: str, **attrs) -> None:
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)

    module("sb.store.db", reset_db=lambda: calls.append("reset_db"))
    module("sb.hooks", RESET_HOOKS={"edge": lambda: calls.append("edge"), "trap": lambda: calls.append("trap")})
    module("sb.canary.seed", seed_canaries=lambda: calls.append("seed"))

    from sb.demo import reset as reset_mod

    monkeypatch.setattr(reset_mod, "DATASETS_DIR", tmp_path / "datasets")
    evidence_before = snapshot(EVIDENCE)

    result = reset_mod.reset_demo()

    checks = {c["name"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert checks["reset_hook.provenance"]["ok"] is False
    assert "PRV-01" in checks["reset_hook.provenance"]["detail"]
    assert checks["reset_hook.edge"]["ok"] and checks["reset_hook.trap"]["ok"]
    assert calls[:3] == ["reset_db", "edge", "trap"] and "seed" in calls
    assert RUN_ID.match(result["run_id"])
    assert snapshot(EVIDENCE) == evidence_before
