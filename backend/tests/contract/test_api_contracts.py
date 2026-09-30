"""Live FastAPI response validation for all master-plan dashboard GET shapes."""
import json

import httpx
import pytest

from sb import contracts
from sb.canary.registry import list_canaries
from sb.canary.seed import seed_canaries
from sb.main import app
from sb.provenance import evidence
from sb.store import db


@pytest.mark.asyncio
async def test_live_dashboard_get_contracts(tmp_path, monkeypatch, origin_server):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "contracts.sqlite3"))
    db.reset_db()
    seed_canaries()
    canary = list_canaries()[0]
    now = "2026-09-30T10:00:00Z"

    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("SESSION-DEMO-001", "CLIENT-DEMO-001", "192.0.2.10", "Synthetic Browser", "fp-demo", now, now, 1,
             "VERIFIED", "HUMAN_LIKELY", 0, "[]", 0, "[]", json.dumps([{"layer": "ORIGIN", "decision": "ALLOW"}]),
             '["/"]', "[]", "[]", None),
        )
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code, user_agent,
                header_fp, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("EVENT-DEMO-001", now, "SESSION-DEMO-001", "CLIENT-DEMO-001", "192.0.2.10", "GET", "/",
             200, "Synthetic Browser", "fp-demo", "ORIGIN", "ALLOW", 0, "[]"),
        )
        conn.execute("INSERT INTO datasets VALUES (?, ?, ?, ?, ?, ?)",
                     ("DATASET-DEMO-001", "target", "synthetic.jsonl", "c" * 64, 1, now))
        conn.execute("INSERT INTO probe_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("PROBE-DEMO-001", now, now, "target", "DATASET-DEMO-001", "c" * 64,
                      json.dumps({"name": "fixture-model"}), "DONE"))
        conn.execute("INSERT INTO probe_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("RESULT-DEMO-001", "PROBE-DEMO-001", canary.canary_id, "Synthetic question", "[]",
                      "Synthetic answer", "d" * 64, 1, now))
        conn.execute(
            """INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("CASE-DEMO-001", "RUN-DEMO-001", now, "PROVENANCE_SIGNAL_DETECTED", "HIGH", canary.canary_id,
             json.dumps(["SESSION-DEMO-001"]), json.dumps(["PROBE-DEMO-001"]), "[]", "{}", "Synthetic case."),
        )

    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", tmp_path / "evidence")
    evidence.build_bundle({
        "case_id": "CASE-DEMO-001", "run_id": "RUN-DEMO-001", "created_at": now,
        "status": "PROVENANCE_SIGNAL_DETECTED", "confidence": "HIGH", "primary_canary_id": canary.canary_id,
        "bundle": {"canaries": [canary.model_dump()]},
    })

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        cases = [
            ("/api/v1/health", contracts.Health),
            ("/api/v1/overview", contracts.Overview),
            ("/api/v1/traffic/events", contracts.TrafficEvents),
            ("/api/v1/sessions", contracts.SessionList),
            ("/api/v1/sessions/SESSION-DEMO-001", contracts.SessionDetail),
            ("/api/v1/canaries", contracts.CanariesResponse),
            (f"/api/v1/canaries/{canary.canary_id}", contracts.CanaryDetail),
            ("/api/v1/datasets", contracts.DatasetsResponse),
            ("/api/v1/probes", contracts.ProbeListResponse),
            ("/api/v1/probes/PROBE-DEMO-001", contracts.ProbeRun),
            ("/api/v1/cases", contracts.CaseSummaries),
            ("/api/v1/cases/CASE-DEMO-001", contracts.Case),
            ("/api/v1/cases/CASE-DEMO-001/evidence", contracts.CaseEvidenceResponse),
            ("/api/v1/demo/status", contracts.DemoStatus),
        ]
        live = {}
        for path, model in cases:
            response = await client.get(path)
            assert response.status_code == 200, f"{path}: {response.text}"
            # RootModel validates the raw cases array without wrapping its JSON shape.
            live[path] = response.json()
            model.model_validate(live[path])
            if path.endswith("/cases"):
                assert isinstance(live[path], list)

        verify = await client.post("/api/v1/cases/CASE-DEMO-001/verify")
        assert verify.status_code == 200, verify.text
        contracts.EvidenceVerification.model_validate(verify.json())

    # Dashboard handshake: compare the exact live GET values with their durable
    # SQLite sources for this controlled run, rather than just validating shape.
    with db.get_connection() as conn:
        sql_decisions = {
            row["decision"]: row["count"]
            for row in conn.execute(
                "SELECT decision, COUNT(*) AS count FROM traffic_events GROUP BY decision"
            ).fetchall()
        }
        assert live["/api/v1/overview"]["counts"] == {
            name: sql_decisions.get(name, 0) for name in contracts.Decision.__args__
        }
        assert len(live["/api/v1/traffic/events"]["events"]) == conn.execute(
            "SELECT COUNT(*) FROM traffic_events"
        ).fetchone()[0]
        assert len(live["/api/v1/sessions"]["sessions"]) == conn.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]
        assert len(live["/api/v1/canaries"]["canaries"]) == conn.execute(
            "SELECT COUNT(*) FROM canaries"
        ).fetchone()[0]
        assert len(live["/api/v1/datasets"]["datasets"]) == conn.execute(
            "SELECT COUNT(*) FROM datasets"
        ).fetchone()[0]
        assert len(live["/api/v1/probes"]["probes"]) == conn.execute(
            "SELECT COUNT(*) FROM probe_runs"
        ).fetchone()[0]
        assert len(live["/api/v1/cases"]) == conn.execute(
            "SELECT COUNT(*) FROM cases"
        ).fetchone()[0]
        assert len(live[f"/api/v1/canaries/{canary.canary_id}"]["exposures"]) == conn.execute(
            "SELECT COUNT(*) FROM exposures WHERE canary_id = ?", (canary.canary_id,)
        ).fetchone()[0]
        assert len(live["/api/v1/probes/PROBE-DEMO-001"]["results"]) == conn.execute(
            "SELECT COUNT(*) FROM probe_results WHERE probe_id = 'PROBE-DEMO-001'"
        ).fetchone()[0]
        assert len(live["/api/v1/cases/CASE-DEMO-001/evidence"]["objects"]) == conn.execute(
            "SELECT COUNT(*) FROM evidence_objects WHERE case_id = 'CASE-DEMO-001'"
        ).fetchone()[0]
