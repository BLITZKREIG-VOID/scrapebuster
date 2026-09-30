"""Demo runner — master plan §20.

Server side: :func:`start` runs steps 1–7 in a background thread under the run
lock. Every PASS condition is checked via the public API (poll every 0.5 s until
the per-step timeout); attackers run as subprocesses. Each failed step is
retried once and the retry is recorded in the step ``detail``. ``DemoStatus`` is
persisted in ``demo_state`` after every transition.

CLI (``make demo`` / ``make demo-step``), talks to a running backend:

    cd backend && python -m sb.demo.runner              # all steps
    cd backend && python -m sb.demo.runner --step-mode  # Enter between steps
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable

import httpx
from sb.demo import (
    ATTACKS_DIR,
    CONTROL_DATASET,
    DATASETS_DIR,
    EDGE_URL,
    REPO,
    RUN_LOCK,
    DemoBusy,
    get_state,
    set_state,
    utc_now,
)

POLL_S = 0.5
SAFETY_STOP_EXIT_CODE = 3
# (id, name, timeout_s, one-line narration)
STEPS: tuple[tuple[int, str, int, str], ...] = (
    (1, "ordinary_bot", 30, "Scraper 1, a plain HTTP bot, bursts the site: Layer 1 throttles, then blocks it."),
    (2, "advanced_scraper", 60, "Scraper 2, headless browser automation: Layer 2 challenges it and restricts it."),
    (3, "sophisticated_scraper", 120, "Scraper 3, a stealth browser, passes Layer 2, walks into the Layer 3 trap and harvests canaries."),
    (4, "ingest_datasets", 20, "The 'AI company' ingests the scraped dataset as target and a clean dataset as control."),
    (5, "probe", 120, "Doberman asks the target and control models canary questions that never contain the canary text."),
    (6, "case_check", 10, "Correlation engine: the latest case must read PROVENANCE SIGNAL DETECTED."),
    (7, "verify_evidence", 10, "Evidence bundle verification: every hash and the chain link must be VALID."),
)
TERMINAL = ("PASS", "FAIL")


class StepFailed(Exception):
    pass


class SafetyStop(StepFailed):
    """Raised when an attacker step exits with a safety stop (HTTP 429/5xx)."""

    def __init__(self, message: str, summary: dict | None = None):
        super().__init__(message)
        self.summary = summary or {}


def fresh_status(run_id: str | None, mode: str = "live") -> dict:
    return {
        "run_id": run_id,
        "phase": "READY",
        "mode": mode,
        "steps": [
            {"id": sid, "name": name, "status": "PENDING", "detail": "", "started_at": None, "finished_at": None}
            for sid, name, _, _ in STEPS
        ],
    }


def get_status() -> dict:
    return get_state("demo_status") or fresh_status(get_state("run_id"))


def _save(status: dict) -> None:
    set_state("demo_status", status)
    set_state("phase", status["phase"])


def start(step: int | None = None) -> dict:
    """Start a background run (all steps, or one). Raises :class:`DemoBusy` when locked."""
    if step is not None and not 1 <= step <= len(STEPS):
        raise ValueError(f"step must be 1..{len(STEPS)}")
    if not RUN_LOCK.acquire(blocking=False):
        raise DemoBusy("a demo run is already in progress")
    try:
        status = get_status()
        if status.get("mode") == "golden":
            raise DemoBusy("recorded golden run is loaded; POST /api/v1/demo/reset first")
        ids = [step] if step is not None else [sid for sid, *_ in STEPS]
        if step is None:
            status = fresh_status(status.get("run_id"))
        status["phase"] = "RUNNING"
        for s in status["steps"]:
            if s["id"] in ids:
                s.update(status="PENDING", detail="", started_at=None, finished_at=None)
        _save(status)
    except BaseException:
        RUN_LOCK.release()
        raise
    threading.Thread(target=_run_locked, args=(status, ids), name="sb-demo-runner", daemon=True).start()
    return status


def _run_locked(status: dict, ids: list[int]) -> None:
    try:
        Runner(status).run(ids)
    finally:
        RUN_LOCK.release()


class Runner:
    def __init__(self, status: dict, base_url: str = EDGE_URL):
        self.status = status
        self.api = httpx.Client(base_url=base_url, timeout=10)
        self.ctx: dict = get_state("demo_context") or {}
        self.handlers: dict[int, Callable[[float], str]] = {
            1: self.step_ordinary_bot,
            2: self.step_advanced_scraper,
            3: self.step_sophisticated_scraper,
            4: self.step_ingest,
            5: self.step_probe,
            6: self.step_case,
            7: self.step_verify,
        }

    # ── orchestration ────────────────────────────────────────────────
    def run(self, ids: list[int]) -> None:
        try:
            for sid in ids:
                if not self.run_step(sid):
                    self.status["phase"] = "FAILED"
                    return
            steps = self.status["steps"]
            self.status["phase"] = "COMPLETE" if all(s["status"] == "PASS" for s in steps) else "PAUSED"
        except Exception as exc:  # noqa: BLE001 - never leave the status stuck in RUNNING
            self.status["phase"] = "FAILED"
            for s in self.status["steps"]:
                if s["status"] == "RUNNING":
                    s.update(status="FAIL", detail=f"{s['detail']} | runner error: {exc!r}", finished_at=utc_now())
        finally:
            _save(self.status)
            self.api.close()

    def run_step(self, sid: int) -> bool:
        step = self.status["steps"][sid - 1]
        timeout = STEPS[sid - 1][2]
        step.update(status="RUNNING", detail="", started_at=utc_now(), finished_at=None)
        _save(self.status)
        notes: list[str] = []
        for attempt in (1, 2):  # at most one automatic retry, always logged
            try:
                detail = self.handlers[sid](time.monotonic() + timeout)
            except SafetyStop as exc:
                notes.append(f"safety stop (no retry): {exc}")
                step.update(status="FAIL", detail="; ".join(notes), finished_at=utc_now())
                _save(self.status)
                return False
            except Exception as exc:  # noqa: BLE001 - any ordinary step failure is logged and retried once
                notes.append(f"attempt {attempt} FAIL: {exc}")
                if attempt == 1:
                    notes.append("retrying once")
                    step["detail"] = "; ".join(notes)
                    _save(self.status)
                    continue
                step.update(status="FAIL", detail="; ".join(notes), finished_at=utc_now())
                _save(self.status)
                return False
            notes.append(f"attempt {attempt} PASS: {detail}" if attempt == 2 else detail)
            step.update(status="PASS", detail="; ".join(notes), finished_at=utc_now())
            set_state("demo_context", self.ctx)
            _save(self.status)
            return True
        return False

    # ── helpers ──────────────────────────────────────────────────────
    def wait_for(self, predicate: Callable[[], object], deadline: float, what: str):
        last = None
        while True:
            try:
                result = predicate()
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                result, last = None, f"{exc.__class__.__name__}: {exc}"
            if result:
                return result
            if time.monotonic() >= deadline:
                raise StepFailed(f"timeout waiting for {what}" + (f" (last error: {last})" if last else ""))
            time.sleep(POLL_S)

    def get(self, path: str, **params):
        resp = self.api.get(path, params=params or None)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict | None, deadline: float):
        resp = self.api.post(path, json=body or {}, timeout=max(1.0, deadline - time.monotonic()))
        if resp.status_code >= 400:
            raise StepFailed(f"POST {path} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    @staticmethod
    def items(payload, key: str) -> list:
        return payload[key] if isinstance(payload, dict) else payload

    def attacker(self, script: str, args: list[str], deadline: float) -> dict:
        cmd = [sys.executable, str(ATTACKS_DIR / script), "--base", EDGE_URL, *args]
        try:
            proc = subprocess.run(
                cmd, cwd=REPO, capture_output=True, text=True, check=False,
                timeout=max(1.0, deadline - time.monotonic()),
            )
        except subprocess.TimeoutExpired as exc:
            raise StepFailed(f"{script} timed out") from exc
        if proc.returncode == SAFETY_STOP_EXIT_CODE:
            stderr_diag = proc.stderr.strip()[-400:]
            lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
            partial = f" | partial: {lines[-1]}" if lines else ""
            summary = json.loads(lines[-1]) if lines else {}
            raise SafetyStop(f"{script} safety stop (exit {proc.returncode}): {stderr_diag}{partial}", summary)
        if proc.returncode != 0:
            raise StepFailed(f"{script} exit {proc.returncode}: {proc.stderr.strip()[-400:]}")
        lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
        return json.loads(lines[-1]) if lines else {}

    def session_with(self, classification: str, state: str | None = None):
        def check():
            for s in self.items(self.get("/api/v1/sessions"), "sessions"):
                if s.get("classification") == classification and (state is None or s.get("state") == state):
                    return s
            return None
        return check

    def exposure_count(self) -> int:
        total = 0
        for canary in self.items(self.get("/api/v1/canaries"), "canaries"):
            detail = self.get(f"/api/v1/canaries/{canary['canary_id']}")
            total += len(detail.get("exposures") or [])
        return total

    def latest_case(self):
        cases = self.items(self.get("/api/v1/cases"), "cases")
        return max(cases, key=lambda c: c.get("created_at") or "") if cases else None

    # ── steps (§20) ──────────────────────────────────────────────────
    def step_ordinary_bot(self, deadline: float) -> str:
        stopped = None
        try:
            out = self.attacker("ordinary_bot.py", ["--requests", "100", "--threads", "10"], deadline)
        except SafetyStop as exc:
            stopped = exc
            out = exc.summary
            histogram = out.get("status_histogram", {})
            if (
                out.get("content_bodies") != 0
                or set(histogram) != {"403", "429"}
                or not all(histogram.values())
            ):
                raise
        s = self.wait_for(self.session_with("BOT_BASIC", "BLOCKED"), deadline, "session BOT_BASIC/BLOCKED")
        if stopped is not None:
            # A client-side 429 is ambiguous. Accept only the expected stopped
            # batch when persisted L1 events prove every response was enforcement.
            detail = self.get(f"/api/v1/sessions/{s['session_id']}")
            events = self.items(self.get("/api/v1/traffic/events", limit=200), "events")
            events = [e for e in events if e["session_id"] == s["session_id"]]
            actual = {code: sum(str(e["status_code"]) == code for e in events) for code in ("403", "429")}
            if (
                detail.get("user_agent") != out.get("user_agent")
                or actual != out["status_histogram"]
                or len(events) != out.get("requests")
                or any(e["layer"] != "L1" or e["decision"] not in ("THROTTLE", "BLOCK") for e in events)
            ):
                raise stopped
        note = "; bounded client stopped on proven L1 enforcement, no retry" if stopped else ""
        return f"session {s.get('session_id')} BOT_BASIC/BLOCKED; statuses {out.get('status_histogram')}{note}"

    def step_advanced_scraper(self, deadline: float) -> str:
        out = self.attacker("advanced_scraper.py", ["--pages", "6"], deadline)
        s = self.wait_for(self.session_with("AUTOMATION", "RESTRICTED"), deadline, "session AUTOMATION/RESTRICTED")
        return f"session {s.get('session_id')} AUTOMATION/RESTRICTED; content pages {out.get('content_pages')}"

    def step_sophisticated_scraper(self, deadline: float) -> str:
        run_id = self.status.get("run_id") or get_state("run_id") or "RUN-unknown"
        dataset = DATASETS_DIR / f"{run_id}_scraper3.jsonl"
        args = ["--out", str(dataset)]
        if os.environ.get("SB_DEMO_HEADLESS", "").lower() in ("1", "true", "yes"):
            args.append("--headless")
        out = self.attacker("sophisticated_scraper.py", args, deadline)
        s = self.wait_for(self.session_with("SOPHISTICATED_SCRAPER"), deadline, "session SOPHISTICATED_SCRAPER")
        n = self.wait_for(lambda: (c := self.exposure_count()) >= 5 and c, deadline, ">= 5 exposures")
        if not dataset.is_file():
            raise StepFailed(f"dataset file missing: {dataset}")
        self.ctx["dataset_path"] = str(dataset)
        return (
            f"session {s.get('session_id')} SOPHISTICATED_SCRAPER; {n} exposures; "
            f"{out.get('records')} records; anchors {out.get('anchors_found')}"
        )

    def step_ingest(self, deadline: float) -> str:
        dataset = self.ctx.get("dataset_path")
        if not dataset:
            raise StepFailed("no scraper 3 dataset recorded; run step 3 first")
        target = self.post("/api/v1/datasets/ingest", {"path": dataset, "role": "target"}, deadline)
        control = self.post("/api/v1/datasets/ingest", {"path": str(CONTROL_DATASET), "role": "control"}, deadline)
        ids = {target["dataset_id"], control["dataset_id"]}
        self.wait_for(
            lambda: ids <= {d["dataset_id"] for d in self.items(self.get("/api/v1/datasets"), "datasets")},
            deadline, "2 datasets registered",
        )
        self.ctx.update(target_dataset_id=target["dataset_id"], control_dataset_id=control["dataset_id"])
        return f"target {target['dataset_id']} ({target.get('records')} records), control {control['dataset_id']}"

    def step_probe(self, deadline: float) -> str:
        body = {k: self.ctx[k] for k in ("target_dataset_id", "control_dataset_id") if k in self.ctx}
        resp = self.post("/api/v1/probes/run", body, deadline)
        probe_ids = resp["probe_ids"]
        for pid in (probe_ids["target"], probe_ids["control"]):
            self.wait_for(
                lambda pid=pid: self.get(f"/api/v1/probes/{pid}").get("status") == "DONE",
                deadline, f"probe {pid} DONE",
            )
        if resp.get("case_id"):
            self.ctx["case_id"] = resp["case_id"]
        return f"probes {probe_ids['target']} + {probe_ids['control']} DONE; case {resp.get('case_id')}"

    def step_case(self, deadline: float) -> str:
        case = self.wait_for(
            lambda: (c := self.latest_case()) and c.get("status") == "PROVENANCE_SIGNAL_DETECTED" and c,
            deadline, "latest case PROVENANCE_SIGNAL_DETECTED",
        )
        self.ctx["case_id"] = case["case_id"]
        return f"case {case['case_id']} {case['status']} ({case.get('confidence')})"

    def step_verify(self, deadline: float) -> str:
        case_id = self.ctx.get("case_id") or (self.latest_case() or {}).get("case_id")
        if not case_id:
            raise StepFailed("no case to verify")
        result = self.post(f"/api/v1/cases/{case_id}/verify", None, deadline)
        if result.get("result") != "VALID":
            failed = [c.get("name") for c in result.get("checks", []) if not c.get("ok")]
            raise StepFailed(f"verify {result.get('result')}; failed checks {failed}")
        return f"case {case_id} evidence VALID ({len(result.get('checks', []))} checks)"


# ── CLI (make demo / make demo-step) ────────────────────────────────────
def _cli() -> int:
    ap = argparse.ArgumentParser(description="Drive the ScapeBusters demo via the running backend.")
    ap.add_argument("--base", default=EDGE_URL)
    ap.add_argument("--step-mode", action="store_true", help="pause for Enter before each step")
    args = ap.parse_args()
    client = httpx.Client(base_url=args.base, timeout=10)
    budget = sum(t for _, _, t, _ in STEPS) * 2 + 60

    def trigger(body: dict) -> bool:
        resp = client.post("/api/v1/demo/run", json=body)
        if resp.status_code != 200:
            print(f"FAIL  POST /api/v1/demo/run {body} -> {resp.status_code} {resp.text}")
            return False
        return True

    def follow(ids: list[int]) -> bool:
        seen: dict[int, str] = {}
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            status = client.get("/api/v1/demo/status").json()
            for s in status["steps"]:
                if s["id"] in ids and seen.get(s["id"]) != s["status"] and s["status"] != "PENDING":
                    seen[s["id"]] = s["status"]
                    print(f"  step {s['id']} {s['name']:<22} {s['status']:<7} {s['detail']}", flush=True)
            if status["phase"] != "RUNNING":
                return all(s["status"] == "PASS" for s in status["steps"] if s["id"] in ids)
            time.sleep(POLL_S)
        print("FAIL  runner did not finish in time")
        return False

    print(f"run {client.get('/api/v1/demo/status').json().get('run_id')}")
    if not args.step_mode:
        for sid, _, _, narration in STEPS:
            print(f"[{sid}] {narration}")
        ok = trigger({}) and follow([sid for sid, *_ in STEPS])
    else:
        ok = True
        for sid, _, _, narration in STEPS:
            print(f"\n[{sid}] {narration}")
            input("      press Enter to run this step ...")
            if not (trigger({"step": sid}) and follow([sid])):
                ok = False
                break
    print("DEMO PASS" if ok else "DEMO FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
